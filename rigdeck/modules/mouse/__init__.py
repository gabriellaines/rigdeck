"""Wireless gaming mice on Compx chips (USB vendor 3554): Pulsar Xlite V3, Attack Shark X11 Ultra.

Settings live in the mouse itself (kept when unplugged or used on another PC), so there's nothing
for the service to re-apply. Before RigDeck first changes a mouse, it saves a backup of the
mouse's settings area to ~/.local/share/rigdeck/mouse-backups/.
"""
from __future__ import annotations

import glob
import os
import time

from ..base import Module, RigdeckError
from . import compx
from .compx import MouseError

BACKUP_DIR = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
                          "rigdeck", "mouse-backups")
RESTORE_SIZE = 192          # settings region; above it is unused (0xff) flash
MAX_STAGES = 8

# Known models: USB product ids, the handshake's model id (cid, mid) and the sensor's DPI range.
MODELS = {
    "x11-ultra": {"name": "Attack Shark X11 Ultra", "pids": {0xF517: "wireless", 0xF515: "cable"},
                  "cid_mid": (124, 11), "dpi": (50, 30000, 60000),    # PAW3950; >30000 in steps of 100
                  "sensor": True},                                     # competitive mode, LP/HP, 20K FPS…
    "pulsar": {"name": "Pulsar Xlite V3", "pids": {0xF509: "wireless", 0xF508: "wireless", 0xF507: "cable"},
               "cid_mid": (6, 15), "dpi": (50, 26000, 26000)},          # PAW3395
}
PIDS = {pid: key for key, m in MODELS.items() for pid in m["pids"]}
# Handshake connection type -> fastest polling rate
MAX_RATE = {0: 1000, 1: 4000, 2: 1000, 3: 8000, 4: 2000, 5: 8000}
LED_MODES = {1: "steady", 2: "breathing"}
# Sensor settings (models with "sensor": True), values as the vendor's configurator offers them
LOD_OPTIONS = [(3, "0.7 mm"), (1, "1 mm"), (2, "2 mm")]                       # PAW3950
COMPETITIVE_TIMES = [(1, "10 s"), (3, "30 s"), (6, "1 min"), (12, "2 min"), (30, "5 min"), (60, "10 min"),
                     (90, "15 min")]                                          # in units of 10 s
SENSOR_MODES = [(0, "Low power"), (1, "High performance")]                   # "Corded" engages by itself
ANGLE_TUNE_RANGE = (-30, 30)
MAX_DEBOUNCE = 15


def connected() -> list[dict]:
    """[{node, pid, model}] for every supported mouse's configuration interface (no I/O)."""
    return [{"node": node, "pid": pid, "model": PIDS[pid]} for node, pid in compx.config_nodes(set(PIDS))]


def _model_name(key: str, info: dict) -> str:
    m = MODELS[key]
    if key == "pulsar" and (info.get("cid"), info.get("mid")) != m["cid_mid"]:
        return "Pulsar wireless mouse"  # same protocol; a model we haven't seen yet
    return m["name"]


def read_state(dev: dict) -> dict:
    """Everything the mouse page shows. Raises MouseError (e.g. asleep)."""
    model = MODELS[dev["model"]]
    with compx.Mouse(dev["node"]) as m:      # the receiver answers the handshake even if the mouse sleeps
        info = m.info
        base = {"node": dev["node"], "model": dev["model"], "name": _model_name(dev["model"], info),
                "connection": model["pids"][dev["pid"]], "pid": f"{dev['pid']:04x}",
                "maxRate": MAX_RATE.get(info.get("type"), 1000), "asleep": False}
        try:
            head = m.read(0, 12)                       # rate, stage count, current stage, …, LOD
        except MouseError:
            return {**base, "asleep": True}
        dpi = m.read(compx.OFF_DPI, MAX_STAGES * 4)
        colors = m.read(compx.OFF_DPI_COLOR, MAX_STAGES * 4)
        led = m.read(compx.OFF_LED_MODE, 8)
        tail = m.read(compx.OFF_DEBOUNCE, 10)      # debounce, motion sync, sleep, angle snap, ripple
        sensor = m.read(compx.OFF_PERF_STATE, 12) + m.read(compx.OFF_FPS20K, 2) if model.get("sensor") else b""
        battery = m.battery()
    count = compx.unpair(head[2:4]) or 1
    lo, simple, top = model["dpi"]
    return {
        **base,
        "battery": battery,
        "rate": compx.RATES.get(compx.unpair(head[0:2])),
        "stageCount": max(1, min(MAX_STAGES, count)),
        "currentStage": compx.unpair(head[4:6]) or 0,
        "stages": [compx.dpi_value(dpi[i * 4:i * 4 + 4]) for i in range(MAX_STAGES)],
        "colors": ["#%02x%02x%02x" % c if (c := compx.color_value(colors[i * 4:i * 4 + 4])) else "#ffffff"
                   for i in range(MAX_STAGES)],
        "dpiMin": lo, "dpiMax": top, "dpiStepLimit": simple,
        "led": {"mode": compx.unpair(led[0:2]) or 1,
                "brightness": _level(compx.unpair(led[2:4])),
                "speed": compx.unpair(led[4:6]) or 3,
                "on": compx.unpair(led[6:8]) == 1},
        "motionSync": compx.unpair(tail[2:4]) == 1,
        "angleSnap": compx.unpair(tail[6:8]) == 1,
        "ripple": compx.unpair(tail[8:10]) == 1,
        "debounce": compx.unpair(tail[0:2]),
        "sensor": _sensor(head, sensor) if sensor else None,
    }


def _sensor(head: bytes, b: bytes) -> dict:
    """X11 Ultra sensor settings from bytes 181..192 and 225..226 (None where unset)."""
    tune = compx.unpair(b[8:10])
    return {"competitive": compx.unpair(b[0:2]) == 1, "competitiveTime": compx.unpair(b[2:4]),
            "sensorMode": compx.unpair(b[4:6]), "angleTuneOn": compx.unpair(b[10:12]) == 1,
            "angleTune": None if tune is None else (tune - 256 if tune > 127 else tune),
            "fps20k": compx.unpair(b[12:14]) == 1, "lod": compx.unpair(head[10:12]),
            "lodOptions": [{"value": v, "label": t} for v, t in LOD_OPTIONS],
            "competitiveTimes": [{"value": v, "label": t} for v, t in COMPETITIVE_TIMES],
            "sensorModes": [{"value": v, "label": t} for v, t in SENSOR_MODES],
            "angleRange": list(ANGLE_TUNE_RANGE), "maxDebounce": MAX_DEBOUNCE}


def read_battery(dev: dict) -> dict:
    """Light read for background polling: identity and battery only (handshake + one request).
    No battery answer means the mouse is asleep (both supported mice report it when awake)."""
    model = MODELS[dev["model"]]
    with compx.Mouse(dev["node"]) as m:
        battery = m.battery()
        info = m.info
    return {"node": dev["node"], "model": dev["model"], "name": _model_name(dev["model"], info),
            "connection": model["pids"][dev["pid"]], "pid": f"{dev['pid']:04x}",
            "maxRate": MAX_RATE.get(info.get("type"), 1000), "battery": battery, "asleep": battery is None}


def _level(stored: int | None) -> int:
    """LED brightness as stored -> slider level 1..10 (nearest)."""
    if stored is None:
        return 5
    return min(range(10), key=lambda i: abs(compx.LED_BRIGHTNESS[i] - stored)) + 1


def backup(m: compx.Mouse, model: str) -> str:
    """Save the settings area to a file (kept: the 20 newest per model). Returns the path."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    path = os.path.join(BACKUP_DIR, f"{model}-{time.strftime('%Y%m%d-%H%M%S')}.bin")
    data = m.backup()
    with open(path, "wb") as f:
        f.write(data)
    for old in sorted(glob.glob(os.path.join(BACKUP_DIR, f"{model}-*.bin")))[:-20]:
        os.remove(old)
    return path


_backed_up: set[str] = set()   # models backed up by this process


def change(dev: dict, changes: dict) -> None:
    """Write settings to the mouse. Keys: rate, stageCount, currentStage, stage (index, dpi),
    color (index, '#rrggbb'), motionSync, angleSnap, ripple, led {mode, brightness, speed, on}."""
    model = MODELS[dev["model"]]
    lo, simple, top = model["dpi"]
    with compx.Mouse(dev["node"]) as m:
        if dev["model"] not in _backed_up:
            backup(m, dev["model"])
            _backed_up.add(dev["model"])
        for key, v in changes.items():
            if key == "rate":
                max_rate = MAX_RATE.get(m.info.get("type"), 1000)
                if v not in compx.RATE_CODES or v > max_rate:
                    raise MouseError(f"polling rate must be one of "
                                     f"{', '.join(str(r) for r in sorted(compx.RATE_CODES) if r <= max_rate)} Hz")
                m.write_pair(compx.OFF_RATE, compx.RATE_CODES[v])
            elif key == "stageCount":
                if not 1 <= v <= MAX_STAGES:
                    raise MouseError(f"1–{MAX_STAGES} DPI stages")
                m.write_pair(compx.OFF_STAGES, v)
                cur = compx.unpair(m.read(compx.OFF_CURRENT_STAGE, 2)) or 0
                if cur >= v:
                    m.write_pair(compx.OFF_CURRENT_STAGE, v - 1)
            elif key == "currentStage":
                count = compx.unpair(m.read(compx.OFF_STAGES, 2)) or 1
                if not 0 <= v < count:
                    raise MouseError(f"stage must be 1–{count}")
                m.write_pair(compx.OFF_CURRENT_STAGE, v)
            elif key == "stage":
                i, dpi = v
                if not 0 <= i < MAX_STAGES:
                    raise MouseError(f"stage must be 1–{MAX_STAGES}")
                try:
                    rec = compx.dpi_record(int(dpi), simple_max=simple, dpi_max=top)
                except ValueError as e:
                    raise MouseError(str(e)) from e
                m.write(compx.OFF_DPI + i * 4, rec)
            elif key == "color":
                i, hexcolor = v
                h = hexcolor.lstrip("#")
                m.write(compx.OFF_DPI_COLOR + i * 4, compx.color_record(tuple(int(h[j:j + 2], 16) for j in (0, 2, 4))))
            elif key in ("motionSync", "angleSnap", "ripple"):
                off = {"motionSync": compx.OFF_MOTION_SYNC, "angleSnap": compx.OFF_ANGLE_SNAP,
                       "ripple": compx.OFF_RIPPLE}[key]
                m.write_pair(off, 1 if v else 0)
            elif key in SENSOR_KEYS:
                if not model.get("sensor"):
                    raise MouseError(f"{model['name']} doesn't have this setting")
                _set_sensor(m, key, v)
            elif key == "led":
                if "mode" in v:
                    m.write_pair(compx.OFF_LED_MODE, int(v["mode"]))
                if "brightness" in v:
                    m.write_pair(compx.OFF_LED_BRIGHTNESS, compx.LED_BRIGHTNESS[max(1, min(10, int(v["brightness"]))) - 1])
                if "speed" in v:
                    m.write_pair(compx.OFF_LED_SPEED, max(1, min(5, int(v["speed"]))))
                if "on" in v or "mode" in v:   # choosing an effect also switches the light on
                    m.write_pair(compx.OFF_LED_STATE, 1 if v.get("on", True) else 0)
            else:
                raise MouseError(f"unknown setting {key}")


SENSOR_KEYS = {"competitive", "competitiveTime", "sensorMode", "fps20k", "angleTune", "angleTuneOn", "lod",
               "debounce"}


def _set_sensor(m: compx.Mouse, key: str, v):
    if key == "competitive":
        m.write_pair(compx.OFF_PERF_STATE, 1 if v else 0)
    elif key == "competitiveTime":
        if v not in dict(COMPETITIVE_TIMES):
            raise MouseError("competitive mode timer: " + ", ".join(t for _, t in COMPETITIVE_TIMES))
        m.write_pair(compx.OFF_PERF_TIME, v)
    elif key == "sensorMode":
        if v not in dict(SENSOR_MODES):
            raise MouseError("sensor mode is low power (0) or high performance (1)")
        m.write_pair(compx.OFF_SENSOR_MODE, v)
    elif key == "fps20k":
        m.write_pair(compx.OFF_FPS20K, 1 if v else 0)
    elif key == "angleTune":
        lo, hi = ANGLE_TUNE_RANGE
        if not lo <= int(v) <= hi:
            raise MouseError(f"angle tuning is {lo}° to {hi}°")
        m.write_pair(compx.OFF_ANGLE_TUNE_STATE, 1)              # as the vendor tool does
        m.write_pair(compx.OFF_ANGLE_TUNE, int(v) % 256)
    elif key == "angleTuneOn":
        m.write_pair(compx.OFF_ANGLE_TUNE_STATE, 1 if v else 0)
    elif key == "lod":
        if v not in dict(LOD_OPTIONS):
            raise MouseError("lift-off distance: " + ", ".join(t for _, t in LOD_OPTIONS))
        m.write_pair(compx.OFF_LOD, v)
    elif key == "debounce":
        if not 0 <= int(v) <= MAX_DEBOUNCE:
            raise MouseError(f"debounce is 0–{MAX_DEBOUNCE} ms")
        m.write_pair(compx.OFF_DEBOUNCE, int(v))


def restore(dev: dict, path: str):
    """Write a backup file's settings area back to the mouse."""
    data = open(path, "rb").read()
    if len(data) < RESTORE_SIZE:
        raise MouseError(f"{path} is not a RigDeck mouse backup")
    with compx.Mouse(dev["node"]) as m:
        m.write(0, data[:RESTORE_SIZE])


# ---- CLI ------------------------------------------------------------------------------

def _pick(n: int | None) -> dict:
    mice = connected()
    if not mice:
        raise RigdeckError("no supported mouse found (Pulsar Xlite V3, Attack Shark X11 Ultra)")
    if n is None:
        return mice[0]
    if not 0 <= n < len(mice):
        raise RigdeckError(f"there are {len(mice)} mice; use --mouse 0…{len(mice) - 1}")
    return mice[n]


def cli_list(a):
    for i, d in enumerate(connected()):
        print(f"{i}  {MODELS[d['model']]['name']}  ({d['node']}, {MODELS[d['model']]['pids'][d['pid']]})")


def cli_status(a):
    s = read_state(_pick(a.mouse))
    print(f"{'Mouse':<16}{s['name']}  ({s['connection']}, {s['node']})")
    if s["asleep"]:
        print(f"{'Status':<16}asleep — move the mouse to wake it, then try again")
        return
    b = s["battery"]
    if b:
        print(f"{'Battery':<16}{b['level']}%" + (" (charging)" if b["charging"] else ""))
    print(f"{'Polling rate':<16}{s['rate']} Hz (up to {s['maxRate']})")
    stages = ", ".join(("▶" if i == s["currentStage"] else "") + str(d) for i, d in enumerate(s["stages"][:s["stageCount"]]))
    print(f"{'DPI stages':<16}{stages}")
    led = s["led"]
    print(f"{'Light':<16}" + (f"{LED_MODES.get(led['mode'], led['mode'])}, brightness {led['brightness']}/10, "
                               f"speed {led['speed']}/5" if led["on"] else "off"))
    for k, label in (("motionSync", "Motion sync"), ("angleSnap", "Angle snapping"), ("ripple", "Ripple control")):
        print(f"{label:<16}{'on' if s[k] else 'off'}")
    sn = s.get("sensor")
    if sn:
        times, modes, lods = dict(COMPETITIVE_TIMES), dict(SENSOR_MODES), dict(LOD_OPTIONS)
        print(f"{'Competitive':<16}{'on' if sn['competitive'] else 'off'} (timer {times.get(sn['competitiveTime'], '?')})")
        print(f"{'Sensor mode':<16}{modes.get(sn['sensorMode'], sn['sensorMode'])}")
        print(f"{'20K FPS scan':<16}{'on' if sn['fps20k'] else 'off'}")
        print(f"{'Lift-off':<16}{lods.get(sn['lod'], sn['lod'])}")
        print(f"{'Angle tuning':<16}" + (f"{sn['angleTune']:+d}°" if sn["angleTuneOn"] else "off"))
        print(f"{'Debounce':<16}{s['debounce']} ms")


def cli_set(a):
    dev = _pick(a.mouse)
    ch: dict = {}
    if a.rate:
        ch["rate"] = a.rate
    if a.dpi:
        stages = [int(x) for x in a.dpi]
        if len(stages) > MAX_STAGES:
            raise ValueError(f"at most {MAX_STAGES} DPI stages")
        for i, d in enumerate(stages):
            ch[f"stage{i}"] = d
        ch["stageCount"] = len(stages)
    if a.stage is not None:
        ch["currentStage"] = a.stage - 1
    for k in ("motion_sync", "angle_snap", "ripple"):
        v = getattr(a, k)
        if v is not None:
            ch[{"motion_sync": "motionSync", "angle_snap": "angleSnap", "ripple": "ripple"}[k]] = v == "on"
    for flag, key in (("competitive", "competitive"), ("fps20k", "fps20k")):
        v = getattr(a, flag)
        if v is not None:
            ch[key] = v == "on"
    if a.sensor_mode:
        ch["sensorMode"] = {"low-power": 0, "high-performance": 1}[a.sensor_mode]
    if a.competitive_time:
        ch["competitiveTime"] = next((v for v, t in COMPETITIVE_TIMES if t.replace(" ", "") == a.competitive_time), None)
        if ch["competitiveTime"] is None:
            raise ValueError("timer: " + ", ".join(t.replace(" ", "") for _, t in COMPETITIVE_TIMES))
    if a.lod:
        ch["lod"] = {"0.7": 3, "1": 1, "2": 2}[a.lod]
    if a.angle_tune is not None:
        ch["angleTune"] = a.angle_tune
    if a.debounce is not None:
        ch["debounce"] = a.debounce
    if a.light:
        ch["led"] = {"on": False} if a.light == "off" else {"mode": {"steady": 1, "breathing": 2}[a.light]}
    if not ch:
        raise ValueError("nothing to change — see `rigdeck mouse set --help`")
    # stage writes go through the "stage" key one at a time
    ordered = {}
    for k, v in ch.items():
        if k.startswith("stage") and k[5:].isdigit():
            change(dev, {"stage": (int(k[5:]), v)})
        else:
            ordered[k] = v
    if ordered:
        change(dev, ordered)
    print("saved on the mouse")


def cli_backup(a):
    dev = _pick(a.mouse)
    with compx.Mouse(dev["node"]) as m:
        print(backup(m, dev["model"]))


def cli_restore(a):
    restore(_pick(a.mouse), a.file)
    print("settings restored from", a.file)


class MouseModule(Module):
    id = "mouse"
    title = "Mouse"
    icon = "mouse"
    kind = "peripheral"
    order = 62
    bluetooth = ("mouse",)

    def detect(self) -> bool:
        return bool(connected())

    def add_cli(self, sub):
        p = sub.add_parser("mouse", help="wireless mice: DPI, polling rate, light, battery")
        ms = p.add_subparsers(dest="mouse_cmd", required=True)
        ms.add_parser("list", help="connected mice").set_defaults(func=cli_list)
        st = ms.add_parser("status", help="battery and settings")
        st.add_argument("--mouse", type=int, metavar="N")
        st.set_defaults(func=cli_status)
        s = ms.add_parser("set", help="change settings (saved on the mouse)")
        s.add_argument("--mouse", type=int, metavar="N", help="which mouse (see `list`), default the first")
        s.add_argument("--rate", type=int, metavar="HZ", help="polling rate: 125 … 8000")
        s.add_argument("--dpi", nargs="+", metavar="DPI", help="DPI stages, e.g. 800 1600 3200")
        s.add_argument("--stage", type=int, metavar="N", help="active DPI stage (1 = first)")
        s.add_argument("--motion-sync", choices=["on", "off"])
        s.add_argument("--angle-snap", choices=["on", "off"])
        s.add_argument("--ripple", choices=["on", "off"])
        s.add_argument("--light", choices=["steady", "breathing", "off"])
        sg = s.add_argument_group("sensor (Attack Shark X11 Ultra)")
        sg.add_argument("--competitive", choices=["on", "off"], help="competitive mode: MCU and sensor at full performance")
        sg.add_argument("--competitive-time", metavar="T", help="competitive mode timer: 10s 30s 1min 2min 5min 10min 15min")
        sg.add_argument("--sensor-mode", choices=["low-power", "high-performance"])
        sg.add_argument("--fps20k", choices=["on", "off"], help="20,000 FPS sensor scan rate")
        sg.add_argument("--lod", choices=["0.7", "1", "2"], help="lift-off distance in mm")
        sg.add_argument("--angle-tune", type=int, metavar="DEG", help="rotate tracking by -30…30 degrees")
        sg.add_argument("--debounce", type=int, metavar="MS", help="button debounce 0–15 ms")
        s.set_defaults(func=cli_set)
        b = ms.add_parser("backup", help="save the mouse's settings to a file")
        b.add_argument("--mouse", type=int, metavar="N")
        b.set_defaults(func=cli_backup)
        r = ms.add_parser("restore", help="write a backup file back to the mouse")
        r.add_argument("file")
        r.add_argument("--mouse", type=int, metavar="N")
        r.set_defaults(func=cli_restore)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "MousePage.qml")

    def qt_backend(self, app):
        from .qt import MouseBackend
        return MouseBackend()
