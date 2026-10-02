"""Logitech G keyboards over HID++ 2.0 (USB): identity, lighting brightness, analog settings.

Supported: PRO X TKL RAPID (046d:c35b). Its onboard profiles' analog settings (actuation point,
Rapid Trigger) are read from the keyboard (see analog.py). RigDeck can also keep its own settings
per onboard profile (`[keyboard.analog.pN]` in config.toml): the keyboard only takes them as *live*
settings, which a profile switch or unplugging wipes, so the service re-applies them whenever that
profile becomes active.
"""
from __future__ import annotations

import logging
import os

from ... import config, servicectl
from ..base import Module, RigdeckError, ServiceTask
from . import analog, hidpp
from .hidpp import HidppError
from .keymap import KEYS

log = logging.getLogger("rigdeck.keyboard")
POLL = 1.0               # how fast a profile switch (Fn+F2/F3/F4) gets RigDeck's settings back
SERVICE_SW_ID = 0x0B

MODELS = {0xC35B: "Logitech G PRO X TKL RAPID"}
# Brightness levels the keyboard's own Fn key cycles through (halving from 100).
BRIGHTNESS_PRESETS = [0, 13, 25, 50, 100]


def connected() -> list[dict]:
    return [{"node": node, "pid": pid, "model": MODELS[pid]} for node, pid in hidpp.interfaces(set(MODELS))]


def read_state(dev: dict) -> dict:
    with hidpp.Device(dev["node"]) as k:
        st = {"node": dev["node"], "pid": f"{dev['pid']:04x}", "name": dev["model"],
              "deviceName": k.name(), "firmware": k.firmware()}
        if k.index(hidpp.BRIGHTNESS) is not None:
            info = k.feature(hidpp.BRIGHTNESS, 0)
            st["brightnessMax"] = int.from_bytes(info[0:2], "big")
            st["brightnessMin"] = int.from_bytes(info[4:6], "big")
            st["brightness"] = int.from_bytes(k.feature(hidpp.BRIGHTNESS, 1)[0:2], "big")
        if k.index(analog.PROFILE_MGMT) is not None:
            st["activeProfile"] = analog.active_profile(k)
    return st


def set_brightness(dev: dict, value: int):
    with hidpp.Device(dev["node"]) as k:
        info = k.feature(hidpp.BRIGHTNESS, 0)
        lo, hi = int.from_bytes(info[4:6], "big"), int.from_bytes(info[0:2], "big")
        if not lo <= value <= hi:
            raise RigdeckError(f"brightness must be {lo}–{hi}")
        k.feature(hidpp.BRIGHTNESS, 2, int(value).to_bytes(2, "big"))


def analog_state(dev: dict) -> list[dict]:
    """Per onboard profile: actuation and Rapid Trigger, keys grouped by value (for display)."""
    every = len(analog.KEYS)

    def groups(values):
        return [{"value": v, "keys": names, "all": len(names) == every} for v, names in analog.summary(values)]
    out = []
    for p in analog.read_profiles(dev["node"]):
        name = "" if p["name"].startswith("PROFILE_NAM") else p["name"]    # G HUB's placeholder
        out.append({"index": p["index"], "keys": p["keys"], "name": name, "actuation": groups(p["actuation"]),
                    "rapidTrigger": groups(p["rapidTrigger"])})
    return out


# ---- RigDeck's own analog settings, per onboard profile ----------------------------------
# [keyboard.analog.p1]  actuation = 20 (0.1 mm, every key), rapid = 5 (0 = Rapid Trigger off)
# [keyboard.analog.p1.keys]  k1d = 10        per-key actuation
# [keyboard.analog.p1.rapid_keys]  k1e = 3   per-key Rapid Trigger (also turns it on for that key)

def custom(n: int, cfg: dict | None = None) -> dict | None:
    """RigDeck's settings for onboard profile n (1–3), or None to leave the keyboard's own."""
    cfg = cfg if cfg is not None else config.load()
    t = cfg.get("keyboard", {}).get("analog", {}).get(f"p{n}")
    if not t or "actuation" not in t:
        return None

    def ids(table):
        return {int(k[1:], 16): int(v) for k, v in (table or {}).items() if k.startswith("k")}
    return {"actuation": int(t["actuation"]), "rapid": int(t.get("rapid", 0)),
            "keys": ids(t.get("keys")), "rapidKeys": ids(t.get("rapid_keys"))}


def effective(s: dict) -> tuple[int, dict[int, int], dict[int, int]]:
    """(default, per-key actuation, per-key Rapid Trigger) to send to the keyboard."""
    rapid = {kid: s["rapid"] for kid in KEYS} if s["rapid"] else {}
    rapid.update(s["rapidKeys"])
    return s["actuation"], dict(s["keys"]), rapid


def save_custom(n: int, s: dict | None):
    """Store (or with None, remove) RigDeck's settings for profile n. Validates first."""
    if s is not None:
        default, keys, rapid = effective(s)
        analog._check({0: default}, analog.ACTUATION_RANGE, "actuation")
        analog._check(keys, analog.ACTUATION_RANGE, "actuation")
        analog._check(rapid, analog.RAPID_RANGE, "Rapid Trigger sensitivity")
    cfg = config.load()
    table = config.section(cfg, "keyboard", "analog")
    table.pop(f"p{n}", None)
    if s is not None:
        table[f"p{n}"] = {"actuation": s["actuation"], "rapid": s["rapid"],
                          "keys": {f"k{k:02x}": v for k, v in sorted(s["keys"].items())},
                          "rapid_keys": {f"k{k:02x}": v for k, v in sorted(s["rapidKeys"].items())}}
    config.save(cfg)


def apply_custom(dev: dict, n: int, sw_id: int = hidpp.SW_ID) -> bool:
    """If profile n is active, put RigDeck's settings for it (or the profile's own) on the keyboard.
    Returns whether n was the active profile."""
    with hidpp.Device(dev["node"], sw_id=sw_id) as k:
        if analog.active_profile(k) != n:
            return False
        s = custom(n)
        if s:
            analog.apply(k, *effective(s))
        else:
            analog.restore(k, n)
    return True


class KeyboardTask(ServiceTask):
    """Keeps RigDeck's analog settings on the keyboard: on plug-in, at login, after a profile switch,
    and when they're changed (the GUI and CLI send SIGHUP)."""

    def __init__(self):
        self.cfg: dict = {}
        self.applied: dict = {}          # node -> (profile, settings) last put on that keyboard

    def reload(self, cfg: dict):
        self.cfg = cfg

    def tick(self, now: float) -> float:
        kbs = connected()
        self.applied = {n: v for n, v in self.applied.items() if n in {d["node"] for d in kbs}}
        wanted_any = any(custom(i, self.cfg) for i in (1, 2, 3))
        for dev in kbs:
            if not wanted_any and dev["node"] not in self.applied:
                continue                  # nothing of ours to keep, and nothing to undo
            try:
                with hidpp.Device(dev["node"], sw_id=SERVICE_SW_ID) as k:
                    n = analog.active_profile(k)
                    want = custom(n, self.cfg)
                    if self.applied.get(dev["node"]) == (n, want):
                        continue
                    if want:
                        analog.apply(k, *effective(want))
                        log.info("profile %d: applied RigDeck's analog settings", n)
                    elif self.applied.get(dev["node"]) and self.applied[dev["node"]][0] == n \
                            and self.applied[dev["node"]][1]:
                        analog.restore(k, n)     # ours were removed while in use: back to the profile's own
                        log.info("profile %d: back to the keyboard's own analog settings", n)
                    if want or wanted_any:
                        self.applied[dev["node"]] = (n, want)
                    else:
                        self.applied.pop(dev["node"], None)
            except (HidppError, OSError) as e:
                log.warning("keyboard: %s", e)
        return POLL


# ---- CLI ------------------------------------------------------------------------------

def _pick() -> dict:
    kbs = connected()
    if not kbs:
        raise RigdeckError("no supported keyboard found (Logitech G PRO X TKL RAPID)")
    return kbs[0]


def cli_status(a):
    s = read_state(_pick())
    print(f"{'Keyboard':<16}{s['name']}  ({s['node']})")
    print(f"{'Firmware':<16}{s['firmware']}")
    if "brightness" in s:
        print(f"{'Brightness':<16}{s['brightness']}%")


def cli_brightness(a):
    set_brightness(_pick(), a.percent)
    print(f"brightness {a.percent}%")


def _tenths(text: str) -> int:
    try:
        return round(float(text.lower().removesuffix("mm").strip()) * 10)
    except ValueError:
        raise ValueError(f"{text!r} is not a distance in mm, e.g. 1.2")


def _key_id(name: str) -> int:
    by_name = {v.lower(): k for k, v in KEYS.items()}
    kid = by_name.get(name.lower())
    if kid is None:
        raise ValueError(f"unknown key {name!r}; names: {' '.join(KEYS.values())}")
    return kid


def _describe(s: dict) -> str:
    default, keys, rapid = effective(s)
    out = f"actuation {analog.mm(default)}"
    if keys:
        out += " (" + ", ".join(f"{KEYS[k]} {analog.mm(v)}" for k, v in sorted(keys.items())) + ")"
    if not rapid:
        return out + ", Rapid Trigger off"
    if s["rapid"]:
        out += f", Rapid Trigger {analog.mm(s['rapid'])} on every key"
        extra = s["rapidKeys"]
    else:
        out += ", Rapid Trigger on"
        extra = rapid
    return out + ("" if not extra else " (" + ", ".join(f"{KEYS[k]} {analog.mm(v)}" for k, v in sorted(extra.items())) + ")")


def cli_analog(a):
    dev = _pick()
    with hidpp.Device(dev["node"]) as k:
        active = analog.active_profile(k)
    for p in analog_state(dev):
        mine = custom(p["index"])
        print(f"Profile {p['index']} ({p['keys']})" + (f"  {p['name']}" if p["name"] else "")
              + ("  ← active" if p["index"] == active else ""))
        if mine:
            print(f"  {'RigDeck':<15}{_describe(mine)}  (in use; the keyboard's own below)")
        for label, groups in (("Actuation", p["actuation"]), ("Rapid Trigger", p["rapidTrigger"])):
            if not groups:
                print(f"  {label:<15}off")
            for i, g in enumerate(groups):
                keys = "all keys" if g["all"] else ", ".join(g["keys"])
                print(f"  {label if i == 0 else '':<15}{g['value']:<8}{keys}")


def cli_analog_set(a):
    s = custom(a.profile) or {"actuation": 20, "rapid": 0, "keys": {}, "rapidKeys": {}}
    if a.actuation:
        s["actuation"] = _tenths(a.actuation)
    if a.rapid:
        s["rapid"] = 0 if a.rapid.lower() == "off" else _tenths(a.rapid)
        if s["rapid"] == 0 and a.rapid.lower() == "off":
            s["rapidKeys"] = {}
    for item in a.key or []:
        name, _, v = item.partition("=")
        kid = _key_id(name.strip())
        if v.strip().lower() in ("", "default"):
            s["keys"].pop(kid, None)
        else:
            s["keys"][kid] = _tenths(v)
    for item in a.rapid_key or []:
        name, _, v = item.partition("=")
        kid = _key_id(name.strip())
        if v.strip().lower() in ("", "off", "default"):
            s["rapidKeys"].pop(kid, None)
        else:
            s["rapidKeys"][kid] = _tenths(v)
    save_custom(a.profile, s)
    servicectl.reload()
    now = apply_custom(_pick(), a.profile)
    print(f"profile {a.profile}: {_describe(s)}"
          + ("" if now else f"\n(applied when profile {a.profile} is active: {analog.PROFILE_KEYS[a.profile - 1]})"))


def cli_analog_reset(a):
    save_custom(a.profile, None)
    servicectl.reload()
    apply_custom(_pick(), a.profile)
    print(f"profile {a.profile}: back to the keyboard's own analog settings")


def cli_features(a):
    with hidpp.Device(_pick()["node"]) as k:
        for fid, flags, ver in k.features():
            hidden = " (hidden)" if flags & 0x40 else ""
            print(f"0x{fid:04x}  v{ver}{hidden}")


class KeyboardModule(Module):
    id = "keyboard"
    title = "Keyboard"
    icon = "keyboard"
    kind = "peripheral"
    order = 61
    bluetooth = ("keyboard",)

    def detect(self) -> bool:
        return bool(connected())

    def service_task(self):
        return KeyboardTask()

    def add_cli(self, sub):
        p = sub.add_parser("keyboard", help="Logitech G keyboard: lighting brightness, analog settings")
        ks = p.add_subparsers(dest="keyboard_cmd", required=True)
        ks.add_parser("status", help="model, firmware, brightness").set_defaults(func=cli_status)
        b = ks.add_parser("brightness", help="lighting brightness in percent (0 = off)")
        b.add_argument("percent", type=int)
        b.set_defaults(func=cli_brightness)
        ks.add_parser("analog", help="actuation points and Rapid Trigger of each onboard profile")\
            .set_defaults(func=cli_analog)
        st = ks.add_parser("analog-set", help="RigDeck's own actuation / Rapid Trigger for an onboard profile, "
                           "e.g. --profile 1 --actuation 1.2 --rapid 0.3 --key W=0.8 --key Space=2.5")
        st.add_argument("--profile", type=int, choices=(1, 2, 3), required=True,
                        help="1 = Fn+F2, 2 = Fn+F3, 3 = Fn+F4")
        st.add_argument("--actuation", metavar="MM", help="every key's actuation point (0.1–4.0)")
        st.add_argument("--rapid", metavar="MM|off", help="Rapid Trigger sensitivity for every key, or off")
        st.add_argument("--key", action="append", metavar="KEY=MM", help="one key's actuation (KEY=default removes)")
        st.add_argument("--rapid-key", action="append", metavar="KEY=MM",
                        help="Rapid Trigger for one key (KEY=off removes)")
        st.set_defaults(func=cli_analog_set)
        rs = ks.add_parser("analog-reset", help="drop RigDeck's settings for a profile (keyboard's own again)")
        rs.add_argument("--profile", type=int, choices=(1, 2, 3), required=True)
        rs.set_defaults(func=cli_analog_reset)
        ks.add_parser("features", help="list the keyboard's HID++ features (for developers)")\
            .set_defaults(func=cli_features)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "KeyboardPage.qml")

    def qt_backend(self, app):
        from .qt import KeyboardBackend
        return KeyboardBackend()
