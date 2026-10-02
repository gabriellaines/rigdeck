"""Monitors over DDC/CI (through ddcutil): brightness, contrast, color preset, input, volume.

Each monitor shows the controls it declares in its capabilities. Settings live in the monitor
itself, so there's nothing for the service to re-apply. Input names come from the monitor and
can be wrong (an LG UltraGear calls its DisplayPort "DVI-1"), so input changes revert by
themselves unless confirmed — see the GUI.
"""
from __future__ import annotations

import os

from ... import vibrance
from ..base import Module, RigdeckError
from . import ddc

# Controls RigDeck offers, in display order: code -> (key, label, kind)
CONTROLS = {
    ddc.BRIGHTNESS: ("brightness", "Brightness", "range"),
    ddc.CONTRAST: ("contrast", "Contrast", "range"),
    ddc.PRESET: ("preset", "Color preset", "choice"),
    ddc.VOLUME: ("volume", "Volume", "range"),
    ddc.MUTE: ("mute", "Mute", "switch"),
    ddc.INPUT: ("input", "Input", "choice"),
}
KEYS = {v[0]: code for code, v in CONTROLS.items()}
MUTE_ON, MUTE_OFF = 1, 2           # MCCS: 01 = muted, 02 = not muted
BRANDS = {"GSM": "LG", "AOC": "AOC", "DEL": "Dell", "SAM": "Samsung", "SEC": "Samsung", "AUS": "ASUS",
          "ACI": "ASUS", "BNQ": "BenQ", "GBT": "Gigabyte", "MSI": "MSI", "HWP": "HP", "HPN": "HP",
          "LEN": "Lenovo", "PHL": "Philips", "VSC": "ViewSonic", "ACR": "Acer", "IVM": "iiyama",
          "NEC": "NEC", "EIZ": "EIZO", "SNY": "Sony", "XMI": "Xiaomi"}

_caps: dict[tuple, dict] = {}   # capabilities per (mfg, model, serial); they never change


def _name(d: dict) -> str:
    brand = BRANDS.get(d["mfg"], d["mfg"])
    model = d["model"].strip()
    return model if model.upper().startswith(brand.upper()) else f"{brand} {model}".strip()


def monitors() -> list[dict]:
    """Connected monitors that answer DDC/CI, each with its controls and current values."""
    out = []
    for d in ddc.detect():
        ident = (d["mfg"], d["model"], d["serial"])
        if ident not in _caps:
            _caps[ident] = ddc.capabilities(d["bus"])
        caps = _caps[ident]
        codes = [c for c in CONTROLS if c in caps]
        values = ddc.get(d["bus"], codes) if codes else {}
        controls = []
        for code in codes:
            key, label, kind = CONTROLS[code]
            v = values.get(code)
            if v is None:
                continue                      # declared but doesn't answer
            c = {"code": code, "key": key, "label": label, "kind": kind, "value": v["cur"]}
            if kind == "range":
                c["max"] = v["max"] or 100
            elif kind == "choice":
                opts = [{"value": k, "label": lbl} for k, lbl in sorted(caps[code]["values"].items())]
                if v["cur"] not in [o["value"] for o in opts]:
                    opts.append({"value": v["cur"], "label": f"Current ({v['cur']:#04x})"})
                if len(opts) < 2:
                    continue
                c["options"] = opts
            elif kind == "switch":
                c["value"] = 1 if v["cur"] == MUTE_ON else 0
            controls.append(c)
        out.append({"id": ":".join(ident), "name": _name(d), "connector": d["connector"], "bus": d["bus"],
                    "serial": d["serial"], "controls": controls})
    return out


def set_value(bus: int, code: int, value: int):
    if code == ddc.MUTE:
        value = MUTE_ON if value else MUTE_OFF
    ddc.set(bus, code, value)


# ---- CLI ------------------------------------------------------------------------------

def _all() -> list[dict]:
    mons = monitors()
    if not mons:
        raise RigdeckError("no monitor answers DDC/CI (turn on DDC/CI in the monitor's menu?)")
    return mons


def _pick(n: int | None) -> list[dict]:
    mons = _all()
    if n is None:
        return mons
    if not 0 <= n < len(mons):
        raise RigdeckError(f"there are {len(mons)} monitors; use 0…{len(mons) - 1}")
    return [mons[n]]


def _shown(c: dict) -> str:
    if c["kind"] == "range":
        return f"{c['value']} / {c['max']}"
    if c["kind"] == "switch":
        return "on" if c["value"] else "off"
    return next((o["label"] for o in c["options"] if o["value"] == c["value"]), str(c["value"]))


def cli_status(a):
    for i, m in enumerate(_pick(a.monitor)):
        print(f"{i}  {m['name']}  ({m['connector']}, /dev/i2c-{m['bus']})")
        for c in m["controls"]:
            extra = ("   choices: " + ", ".join(f"{o['value']}={o['label']}" for o in c["options"])
                     if c["kind"] == "choice" else "")
            print(f"     {c['key']:<12}{_shown(c)}{extra}")


def cli_set(a):
    targets = _pick(a.monitor)
    for item in a.values:
        k, _, v = item.partition("=")
        if k not in KEYS or not v:
            raise ValueError(f"use KEY=VALUE with KEY one of {', '.join(KEYS)} (got {item!r})")
        value = {"on": 1, "off": 0}.get(v.lower())
        value = int(v, 0) if value is None else value
        for m in targets:
            c = next((c for c in m["controls"] if c["key"] == k), None)
            if c is None:
                print(f"{m['name']}: no {k} control — skipped")
                continue
            if c["kind"] == "range" and not 0 <= value <= c["max"]:
                raise ValueError(f"{k} is 0–{c['max']}")
            set_value(m["bus"], c["code"], value)
            print(f"{m['name']}: {k} = {v}")


def cli_vibrance(a):
    if not vibrance.available():
        raise RigdeckError("colour vibrance needs KDE Plasma on Wayland (kscreen-doctor)")
    outs = vibrance.outputs()
    if a.level is None:
        for o in outs:
            note = " (HDR on: not available)" if o["hdr"] else ""
            print(f"{o['name']:<10}{o['level']}%" + ("  (normal)" if o["level"] == vibrance.NEUTRAL else "") + note)
        return
    if not 0 <= a.level <= 100:
        raise ValueError("vibrance is 0–100 % (50 = normal, like NVIDIA's Digital Vibrance)")
    targets = [o["name"] for o in outs if a.monitor in (None, o["name"])]
    if not targets:
        raise RigdeckError(f"no monitor {a.monitor}; see `rigdeck monitor vibrance`")
    for name in targets:
        vibrance.apply(name, a.level)
        print(f"{name}: vibrance {a.level}%")


class MonitorModule(Module):
    id = "monitor"
    title = "Monitors"
    icon = "monitor-cog"
    kind = "peripheral"
    order = 64

    def detect(self) -> bool:
        return (ddc.installed() and os.path.isdir("/sys/class/drm")) or vibrance.available()

    def add_cli(self, sub):
        p = sub.add_parser("monitor", help="monitor brightness, contrast, color preset, input (DDC/CI)")
        ms = p.add_subparsers(dest="monitor_cmd", required=True)
        st = ms.add_parser("status", help="monitors and their settings")
        st.add_argument("monitor", type=int, nargs="?", help="which monitor (default: all)")
        st.set_defaults(func=cli_status)
        s = ms.add_parser("set", help="e.g. brightness=40 contrast=70 (all monitors unless --monitor)")
        s.add_argument("values", nargs="+", metavar="KEY=VALUE")
        s.add_argument("--monitor", type=int, metavar="N")
        s.set_defaults(func=cli_set)
        v = ms.add_parser("vibrance", help="colour vibrance like NVIDIA's Digital Vibrance (50 = normal)")
        v.add_argument("level", type=int, nargs="?", help="0–100; omit to show the current levels")
        v.add_argument("--monitor", metavar="NAME", help="connector, e.g. DP-2 (default: all)")
        v.set_defaults(func=cli_vibrance)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "MonitorPage.qml")

    def qt_backend(self, app):
        from .qt import MonitorBackend
        return MonitorBackend()
