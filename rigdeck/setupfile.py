"""Settings files: every device's settings in one JSON file, to set everything up at once.

`export()` writes what's set now; `check()` finds every mistake in a file before anything is
changed; `apply()` sets each device and reports per section. Every section is optional, so a
file can be as small as `{"mice": [{"dpi": [800, 1600]}]}`. The format is described in
docs/settings-file.md.
"""
from __future__ import annotations

import difflib
import json
import re

from . import config, servicectl

FORMAT = 1
COLOR_HELP = 'a colour like "ff0000" or "#00c8ff"'


class FileError(ValueError):
    """The file can't be used; nothing was changed. `problems` lists every mistake found."""

    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def _mm(v) -> int:
    """1.2 (mm) -> 12 (0.1 mm)."""
    return round(float(v) * 10)


def _off(v) -> bool:
    return v is False or v == 0 or (isinstance(v, str) and v.lower() == "off")


def _is_color(v) -> bool:
    try:
        config.parse_color(str(v))
        return isinstance(v, str)
    except ValueError:
        return False


def _hex(v: str) -> str:
    return v.lstrip("#").lower()


class _Checker:
    """Collects every problem with the path to it, e.g. `mice[0].dpi: …`."""

    def __init__(self):
        self.problems: list[str] = []

    def bad(self, path: str, msg: str):
        self.problems.append(f"{path}: {msg}")

    def table(self, d, path: str, allowed: dict) -> bool:
        """d must be an object whose keys are in `allowed` ({key: check(value, path)})."""
        if not isinstance(d, dict):
            self.bad(path, "should be an object { … }")
            return False
        for k, v in d.items():
            if k not in allowed:
                near = difflib.get_close_matches(k, list(allowed), 1)
                self.bad(f"{path}.{k}", "unknown setting" + (f" — did you mean {near[0]!r}?" if near else
                                                             f"; possible: {', '.join(allowed)}"))
            elif allowed[k]:
                allowed[k](v, f"{path}.{k}")
        return True

    def choice(self, options):
        opts = [str(o) for o in options]

        def check(v, path):
            if str(v).lower() not in opts:
                self.bad(path, f"{v!r} isn't one of: {', '.join(opts)}")
        return check

    def number(self, lo, hi, integer=True, unit=""):
        def check(v, path):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or (integer and float(v) != int(v)):
                self.bad(path, f"should be a {'whole ' if integer else ''}number")
            elif not lo <= v <= hi:
                self.bad(path, f"{v} is outside {lo}–{hi}{unit}")
        return check

    def boolean(self, v, path):
        if not isinstance(v, bool):
            self.bad(path, "should be true or false")

    def color(self, v, path):
        if not _is_color(v):
            self.bad(path, f"should be {COLOR_HELP}")

    def colors_by_name(self, names):
        def check(v, path):
            if self.table(v, path, {n: None for n in names}):
                for k, c in v.items():
                    if k in names:
                        self.color(c, f"{path}.{k}")
        return check

    def mm_or_off(self, lo, hi):
        def check(v, path):
            if _off(v):
                return
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= _mm(v) <= hi:
                self.bad(path, f'should be a distance {lo / 10}–{hi / 10} (mm), or "off"')
        return check


# ---- cooler ---------------------------------------------------------------------------

def _cooler_names():
    from .modules.waterforce import mode_name
    from .modules.waterforce.device import FAN_MODES, PUMP_MODES
    fan = [mode_name(m) for m in FAN_MODES]
    return fan + ["custom"], [mode_name(m) for m in PUMP_MODES]


def _check_cooler(c: _Checker, d, path):
    from .modules.waterforce import effects
    fan, pump = _cooler_names()

    def curve(v, p):
        if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, list) and len(x) == 2 for x in v)):
            c.bad(p, "should be 4 points [temperature °C, fan rpm], e.g. [[30, 1000], [50, 1400], [65, 1900], [80, 2500]]")
            return
        for i, (t, rpm) in enumerate(v):
            c.number(0, 100, unit=" °C")(t, f"{p}[{i}][0]")
            c.number(0, 3200, unit=" rpm")(rpm, f"{p}[{i}][1]")
        if all(isinstance(x[0], (int, float)) for x in v) and [x[0] for x in v] != sorted({x[0] for x in v}):
            c.bad(p, "temperatures should go up from point to point")

    def lighting(v, p):
        c.table(v, p, {"effect": c.choice(effects.ALL), "color": c.color,
                       "brightness": c.number(0, 100, unit=" %"), "speed": c.number(1, 10)})
    c.table(d, path, {"fan": c.choice(fan), "pump": c.choice(pump), "curve": curve, "lighting": lighting})


def _apply_cooler(d) -> str:
    from .modules.waterforce import MODE_NAMES, set_led
    from .modules.waterforce.device import Cooler, SpeedMode, SpeedType
    done = []
    if {"fan", "pump", "curve"} & set(d):
        with Cooler() as cooler:
            fan, pump = cooler.modes()
            if "fan" in d:
                name = d["fan"].lower()
                fan = SpeedMode.CUSTOMIZED if name == "custom" else MODE_NAMES[name]
            if "pump" in d:
                pump = MODE_NAMES[d["pump"].lower()]
            if "curve" in d:
                fan = SpeedMode.CUSTOMIZED
            curve = [tuple(int(x) for x in p) for p in d["curve"]] if "curve" in d else \
                (cooler.curve(SpeedType.FAN) if fan == SpeedMode.CUSTOMIZED else None)
            cooler.set_modes(fan, pump, curve)
        done.append("cooling")
    if "lighting" in d:
        led = {**config.section(config.load(), "cooler", "led"), **d["lighting"]}
        set_led(led.get("effect", "static"), _hex(led["color"]) if led.get("color") else None,
                led.get("brightness"), led.get("speed"))
        done.append("lighting")
    return " and ".join(done)


def _export_cooler() -> dict | None:
    from .modules.waterforce import effects, mode_name
    from .modules.waterforce.device import Cooler, CoolerError, SpeedMode, SpeedType, find_hidraw
    if not find_hidraw():
        return None
    out: dict = {}
    try:
        with Cooler() as cooler:
            fan, pump = cooler.modes()
            out["fan"], out["pump"] = mode_name(fan), mode_name(pump)
            if fan == SpeedMode.CUSTOMIZED:
                out["curve"] = [list(p) for p in cooler.curve(SpeedType.FAN)]
    except CoolerError:
        pass
    out["lighting"] = {**effects.DEFAULTS, **config.section(config.load(), "cooler", "led")}
    return out


# ---- motherboard lighting -------------------------------------------------------------

def _check_motherboard(c: _Checker, d, path):
    from .modules.motherboard import aura

    def zones(v, p):
        if not isinstance(v, dict):
            c.bad(p, 'should be an object of zones, e.g. {"all": {"effect": "static", "color": "ff0000"}}')
            return
        for zone, z in v.items():
            c.table(z, f"{p}.{zone}", {"effect": c.choice(aura.MODES), "color": c.color})
    c.table(d, path, {"lighting": zones})


def _apply_motherboard(d) -> str:
    from .modules.base import RigdeckError
    from .modules.motherboard import lighting, set_lighting
    info = lighting()
    if info is None:
        raise RigdeckError("no ASUS Aura lighting controller found")
    ids = [z["id"] for z in info["zones"]]
    saved = {z["id"]: z for z in info["zones"]}
    zones = d.get("lighting", {})
    for zone, z in zones.items():
        for zid in (ids if zone == "all" else [zone]):
            if zid not in ids:
                raise RigdeckError(f"no lighting zone {zid!r} (this board has: {', '.join(ids)})")
            set_lighting(zid, z.get("effect") or saved[zid]["mode"] or "static",
                         _hex(z.get("color") or saved[zid]["color"]))
    return "lighting"


def _export_motherboard() -> dict | None:
    from .modules.motherboard import aura, lighting
    if not aura.find():
        return None
    zones = {z["id"]: {"effect": z["mode"], "color": z["color"]} for z in (lighting() or {"zones": []})["zones"]
             if z["mode"]}
    return {"lighting": zones} if zones else None


# ---- keyboard -------------------------------------------------------------------------

def _check_keyboard(c: _Checker, d, path):
    from .modules.keyboard import analog
    from .modules.keyboard.keymap import KEYS
    from .modules.keyboard.lighting import LIT_KEYS
    lo, hi = analog.ACTUATION_RANGE
    rlo, rhi = analog.RAPID_RANGE
    act = c.number(lo / 10, hi / 10, integer=False, unit=" mm")
    rapid = c.mm_or_off(rlo, rhi)

    def keys(v, p):
        if c.table(v, p, {n: None for n in KEYS.values()}):
            for name, k in v.items():
                if name in KEYS.values():
                    c.table(k, f"{p}.{name}", {"actuation": act, "rapidTrigger": rapid})

    def profiles(v, p):
        if not isinstance(v, dict):
            c.bad(p, 'should be an object of profiles "1", "2", "3"')
            return
        for n, prof in v.items():
            if n not in ("1", "2", "3"):
                c.bad(f"{p}.{n}", 'profiles are "1" (Fn+F2), "2" (Fn+F3) and "3" (Fn+F4)')
                continue
            c.table(prof, f"{p}.{n}", {"actuation": act, "rapidTrigger": rapid, "keys": keys,
                                       "color": c.color, "keyColors": c.colors_by_name(LIT_KEYS)})
    c.table(d, path, {"brightness": c.number(0, 100, unit=" %"), "profiles": profiles})


def _apply_keyboard(d) -> str:
    from .modules.keyboard import (apply_custom, connected, custom, custom_lighting, save_custom,
                                   save_lighting, set_brightness)
    from .modules.keyboard.keymap import KEYS
    ids = {v: k for k, v in KEYS.items()}
    kbs = connected()
    notes = []
    for n_text, p in (d.get("profiles") or {}).items():
        n = int(n_text)
        if {"actuation", "rapidTrigger", "keys"} & set(p):
            s = custom(n) or {"actuation": 20, "rapid": 0, "keys": {}, "rapidKeys": {}}
            s = {**s, "keys": dict(s["keys"]), "rapidKeys": dict(s["rapidKeys"])}
            if "actuation" in p:
                s["actuation"] = _mm(p["actuation"])
            if "rapidTrigger" in p:
                s["rapid"] = 0 if _off(p["rapidTrigger"]) else _mm(p["rapidTrigger"])
            for name, k in (p.get("keys") or {}).items():
                if "actuation" in k:
                    s["keys"][ids[name]] = _mm(k["actuation"])
                if "rapidTrigger" in k:
                    s["rapidKeys"][ids[name]] = 0 if _off(k["rapidTrigger"]) else _mm(k["rapidTrigger"])
            save_custom(n, s)
        if "color" in p or "keyColors" in p:
            li = custom_lighting(n) or {"base": "ffffff", "keys": {}}
            save_lighting(n, {"base": _hex(p.get("color", li["base"])),
                              "keys": {**li["keys"], **{k: _hex(v) for k, v in (p.get("keyColors") or {}).items()}}})
    if d.get("profiles"):
        servicectl.reload()                    # the service keeps them on after profile switches
        for dev in kbs:
            for n_text in d["profiles"]:
                apply_custom(dev, int(n_text))
        notes.append("profiles")
    if "brightness" in d:
        if kbs:
            set_brightness(kbs[0], int(d["brightness"]))
            notes.append("brightness")
        else:
            notes.append("brightness skipped (keyboard not connected)")
    if d.get("profiles") and not kbs:
        notes.append("used when the keyboard is connected")
    return ", ".join(notes)


def _export_keyboard() -> dict | None:
    from .modules.keyboard import connected, custom, custom_lighting, read_state
    from .modules.keyboard.keymap import KEYS
    out: dict = {}
    kbs = connected()
    if kbs:
        try:
            st = read_state(kbs[0])
            if "brightness" in st:
                out["brightness"] = st["brightness"]
        except OSError:
            pass
    profiles = {}
    for n in (1, 2, 3):
        p: dict = {}
        a = custom(n)
        if a:
            p["actuation"] = a["actuation"] / 10
            p["rapidTrigger"] = a["rapid"] / 10 if a["rapid"] else "off"
            keys: dict = {}
            for kid, v in a["keys"].items():
                keys.setdefault(KEYS[kid], {})["actuation"] = v / 10
            for kid, v in a["rapidKeys"].items():
                keys.setdefault(KEYS[kid], {})["rapidTrigger"] = v / 10 if v else "off"
            if keys:
                p["keys"] = keys
        li = custom_lighting(n)
        if li:
            p["color"] = li["base"]
            if li["keys"]:
                p["keyColors"] = li["keys"]
        if p:
            profiles[str(n)] = p
    if profiles:
        out["profiles"] = profiles
    return out or None


# ---- mice -----------------------------------------------------------------------------

LIGHT_EFFECTS = {"steady": 1, "breathing": 2}


def _lod(v) -> str:
    """Lift-off distance as written (1, 0.7, "2 mm") -> "1", "0.7", "2"."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{float(v):g}"
    return str(v).lower().removesuffix("mm").strip()


def _mouse_tables():
    from .modules.mouse import COMPETITIVE_TIMES, LOD_OPTIONS, SENSOR_MODES
    lod = {t.replace(" mm", ""): v for v, t in LOD_OPTIONS}
    timers = {t: v for v, t in COMPETITIVE_TIMES}
    modes = {t.lower(): v for v, t in SENSOR_MODES}
    return lod, timers, modes


def _check_mice(c: _Checker, d, path):
    from .modules.mouse import ANGLE_TUNE_RANGE, MAX_DEBOUNCE, MAX_STAGES, MODELS
    from .modules.mouse import compx
    lod, timers, modes = _mouse_tables()
    models = [m["name"].lower() for m in MODELS.values()] + list(MODELS)
    if not isinstance(d, list):
        c.bad(path, 'should be a list of mice: [ { "dpi": [800, 1600] }, … ]')
        return

    def dpi(v, p):
        if not isinstance(v, list) or not 1 <= len(v) <= MAX_STAGES:
            c.bad(p, f"should be a list of 1–{MAX_STAGES} DPI values, e.g. [800, 1600, 3200]")
            return
        for i, x in enumerate(v):
            c.number(50, 60000)(x, f"{p}[{i}]")

    def stage_colors(v, p):
        if not isinstance(v, list) or len(v) > MAX_STAGES:
            c.bad(p, f"should be a list of up to {MAX_STAGES} colours")
            return
        for i, x in enumerate(v):
            c.color(x, f"{p}[{i}]")

    def light(v, p):
        c.table(v, p, {"effect": c.choice([*LIGHT_EFFECTS, "off"]), "brightness": c.number(1, 10),
                       "speed": c.number(1, 5)})

    def angle(v, p):
        if not _off(v):
            c.number(*ANGLE_TUNE_RANGE, unit="°")(v, p)

    for i, m in enumerate(d):
        p = f"{path}[{i}]"
        c.table(m, p, {
            "model": c.choice(models), "pollingRate": c.choice(sorted(compx.RATE_CODES)), "dpi": dpi,
            "stage": c.number(1, MAX_STAGES), "stageColors": stage_colors, "light": light,
            "motionSync": c.boolean, "angleSnapping": c.boolean, "rippleControl": c.boolean,
            "liftOff": lambda v, p: c.choice(lod)(_lod(v), p), "debounce": c.number(0, MAX_DEBOUNCE, unit=" ms"),
            "competitive": c.boolean, "competitiveTimer": c.choice(timers),
            "sensorMode": c.choice(modes), "fps20k": c.boolean, "angleTune": angle})
        if isinstance(m, dict) and isinstance(m.get("dpi"), list) and isinstance(m.get("stage"), int) \
                and m["stage"] > len(m["dpi"]):
            c.bad(f"{p}.stage", f"there are only {len(m['dpi'])} DPI stages")


def _apply_mice(entries: list) -> str:
    from .modules.base import RigdeckError
    from .modules.mouse import MODELS, change, connected
    lod, timers, modes = _mouse_tables()
    mice = connected()
    if not mice:
        raise RigdeckError("no supported mouse connected")
    done = []
    for m in entries:
        want = str(m.get("model", "")).lower()
        targets = [dev for dev in mice if not want or want in (dev["model"], MODELS[dev["model"]]["name"].lower())]
        if want and not targets:
            raise RigdeckError(f"{m['model']} isn't connected")
        for dev in targets:
            for i, v in enumerate(m.get("dpi") or []):           # one record per write
                change(dev, {"stage": (i, int(v))})
            for i, v in enumerate(m.get("stageColors") or []):
                change(dev, {"color": (i, "#" + _hex(v))})
            ch: dict = {}
            if "dpi" in m:
                ch["stageCount"] = len(m["dpi"])
            if "stage" in m:
                ch["currentStage"] = int(m["stage"]) - 1
            if "pollingRate" in m:
                ch["rate"] = int(m["pollingRate"])
            for key, name in (("motionSync", "motionSync"), ("angleSnapping", "angleSnap"), ("rippleControl", "ripple"),
                              ("competitive", "competitive"), ("fps20k", "fps20k")):
                if key in m:
                    ch[name] = bool(m[key])
            if "liftOff" in m:
                ch["lod"] = lod[_lod(m["liftOff"])]
            if "debounce" in m:
                ch["debounce"] = int(m["debounce"])
            if "competitiveTimer" in m:
                ch["competitiveTime"] = timers[m["competitiveTimer"]]
            if "sensorMode" in m:
                ch["sensorMode"] = modes[m["sensorMode"].lower()]
            if "angleTune" in m:
                if _off(m["angleTune"]):
                    ch["angleTuneOn"] = False
                else:
                    ch["angleTune"] = int(m["angleTune"])
            if "light" in m:
                li = m["light"]
                led: dict = {k: int(li[k]) for k in ("brightness", "speed") if k in li}
                if li.get("effect") == "off":
                    led["on"] = False
                elif "effect" in li:
                    led["mode"] = LIGHT_EFFECTS[li["effect"]]
                ch["led"] = led
            if ch:
                change(dev, ch)
            done.append(MODELS[dev["model"]]["name"])
    return ", ".join(done)


def _export_mice() -> list | None:
    from .modules.mouse import COMPETITIVE_TIMES, LED_MODES, LOD_OPTIONS, MODELS, SENSOR_MODES, connected, read_state
    out = []
    for dev in connected():
        try:
            s = read_state(dev)
        except OSError:
            continue
        if s["asleep"]:
            continue
        m = {"model": MODELS[dev["model"]]["name"], "pollingRate": s["rate"],
             "dpi": s["stages"][:s["stageCount"]], "stage": s["currentStage"] + 1,
             "stageColors": [_hex(c) for c in s["colors"][:s["stageCount"]]],
             "light": {"effect": LED_MODES.get(s["led"]["mode"], "steady") if s["led"]["on"] else "off",
                       "brightness": s["led"]["brightness"], "speed": s["led"]["speed"]},
             "motionSync": s["motionSync"], "angleSnapping": s["angleSnap"], "rippleControl": s["ripple"],
             "debounce": s["debounce"]}
        sn = s.get("sensor")
        if sn:
            m.update({"liftOff": dict(LOD_OPTIONS).get(sn["lod"], "1 mm").replace(" mm", ""),
                      "competitive": sn["competitive"],
                      "competitiveTimer": dict(COMPETITIVE_TIMES).get(sn["competitiveTime"], "1 min"),
                      "sensorMode": dict(SENSOR_MODES).get(sn["sensorMode"], "High performance").lower(),
                      "fps20k": sn["fps20k"],
                      "angleTune": sn["angleTune"] if sn["angleTuneOn"] and sn["angleTune"] is not None else "off"})
        out.append(m)
    return out or None


# ---- headset --------------------------------------------------------------------------

HEADSET_KEYS = {"sidetone": "sidetone", "autoOffMinutes": "inactive_time", "lights": "lights",
                "voicePrompts": "voice_prompts", "rotateToMute": "rotate_to_mute"}


def _check_headset(c: _Checker, d, path):
    c.table(d, path, {"sidetone": c.number(0, 128), "autoOffMinutes": c.number(0, 90), "lights": c.boolean,
                      "voicePrompts": c.boolean, "rotateToMute": c.boolean})


def _apply_headset(d) -> str:
    from .modules.headset import change
    st = change({HEADSET_KEYS[k]: int(v) for k, v in d.items()})
    return st["name"]


def _export_headset() -> dict | None:
    from .modules.headset import saved
    back = {v: k for k, v in HEADSET_KEYS.items()}
    s = saved()
    return {back[k]: (bool(v) if back[k] in ("lights", "voicePrompts", "rotateToMute") else v)
            for k, v in s.items()} or None


# ---- lighting sync --------------------------------------------------------------------

def _check_lighting(c: _Checker, d, path):
    c.table(d, path, {"sync": c.color})


def _apply_lighting(d) -> str:
    from .modules.base import RigdeckError
    from .modules.lighting import TARGETS, sync
    if "sync" not in d:
        return ""
    errors = sync(_hex(d["sync"]))
    if errors:
        names = {t.id: t.name for t in TARGETS}
        raise RigdeckError("; ".join(f"{names[k]}: {v}" for k, v in errors.items()))
    return f"#{_hex(d['sync'])} on every device"


# ---- the file -------------------------------------------------------------------------

# name: (title, check, apply, export). Applied in this order; the lighting sync goes last so it
# wins over colours set in the device sections.
SECTIONS = {
    "cooler": ("Cooler", _check_cooler, _apply_cooler, _export_cooler),
    "motherboard": ("Motherboard", _check_motherboard, _apply_motherboard, _export_motherboard),
    "keyboard": ("Keyboard", _check_keyboard, _apply_keyboard, _export_keyboard),
    "mice": ("Mice", _check_mice, _apply_mice, _export_mice),
    "headset": ("Headset", _check_headset, _apply_headset, _export_headset),
    "lighting": ("Lighting sync", _check_lighting, _apply_lighting, None),
}


def parse(text: str) -> dict:
    """JSON text -> settings, or FileError listing every problem."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise FileError([f"line {e.lineno}, column {e.colno}: {e.msg} — is it valid JSON?"]) from None
    check(data)
    return data


def check(data) -> None:
    c = _Checker()
    if not isinstance(data, dict):
        raise FileError(["the file should contain one object { … }"])
    allowed = {"rigdeck": None, "$schema": None, **{k: None for k in SECTIONS}}
    c.table(data, "file", allowed)
    if data.get("rigdeck", FORMAT) != FORMAT:
        c.bad("file.rigdeck", f"this RigDeck reads format {FORMAT}; update RigDeck to use this file")
    for name, (_, check_section, _, _) in SECTIONS.items():
        if name in data:
            check_section(c, data[name], name)
    if c.problems:
        raise FileError([p.removeprefix("file.") for p in c.problems])


def apply(data: dict) -> list[dict]:
    """Set everything in the file (already checked). [{section, title, ok, message}] per section;
    one section failing (e.g. a device unplugged) doesn't stop the others."""
    out = []
    for name, (title, _, apply_section, _) in SECTIONS.items():
        if name not in data:
            continue
        try:
            out.append({"section": name, "title": title, "ok": True, "message": apply_section(data[name]) or "done"})
        except Exception as e:
            out.append({"section": name, "title": title, "ok": False, "message": str(e)})
    return out


def export() -> dict:
    """The current settings of every device RigDeck can reach, in the file's format."""
    data: dict = {"rigdeck": FORMAT}
    for name, (_, _, _, export_section) in SECTIONS.items():
        if export_section is None:
            continue
        try:
            v = export_section()
        except Exception:        # a device that can't be read is just left out
            v = None
        if v:
            data[name] = v
    return data


def dumps(data: dict) -> str:
    """Readable JSON: short lists (DPI stages, curve points) and small objects stay on one line."""
    text = json.dumps(data, indent=2)
    text = re.sub(r"\[\s+([^\[\]{}]*?)\s+\]", lambda m: "[" + " ".join(m.group(1).split()) + "]", text)

    def small(m):
        one = "{" + " ".join(m.group(1).split()) + "}"
        return one if len(one) <= 72 else m.group(0)
    return re.sub(r"\{\s+([^\[\]{}]*?)\s+\}", small, text) + "\n"
