"""Logitech G keyboards over HID++ 2.0 (USB): identity, lighting brightness, analog settings.

Supported: PRO X TKL RAPID (046d:c35b). Its analog settings (actuation point, Rapid Trigger) are
shown read-only per onboard profile (see analog.py); changing them is still done on the keyboard
itself (Fn+F5 custom analog profile), which RigDeck explains on the page.
"""
from __future__ import annotations

import os

from ..base import Module, RigdeckError
from . import analog, hidpp
from .hidpp import HidppError

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


def cli_analog(a):
    for p in analog_state(_pick()):
        print(f"Profile {p['index']} ({p['keys']})" + (f"  {p['name']}" if p["name"] else ""))
        for label, groups in (("Actuation", p["actuation"]), ("Rapid Trigger", p["rapidTrigger"])):
            if not groups:
                print(f"  {label:<15}off")
            for i, g in enumerate(groups):
                keys = "all keys" if g["all"] else ", ".join(g["keys"])
                print(f"  {label if i == 0 else '':<15}{g['value']:<8}{keys}")


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

    def add_cli(self, sub):
        p = sub.add_parser("keyboard", help="Logitech G keyboard: lighting brightness, analog settings")
        ks = p.add_subparsers(dest="keyboard_cmd", required=True)
        ks.add_parser("status", help="model, firmware, brightness").set_defaults(func=cli_status)
        b = ks.add_parser("brightness", help="lighting brightness in percent (0 = off)")
        b.add_argument("percent", type=int)
        b.set_defaults(func=cli_brightness)
        ks.add_parser("analog", help="actuation points and Rapid Trigger of each onboard profile")\
            .set_defaults(func=cli_analog)
        ks.add_parser("features", help="list the keyboard's HID++ features (for developers)")\
            .set_defaults(func=cli_features)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "KeyboardPage.qml")

    def qt_backend(self, app):
        from .qt import KeyboardBackend
        return KeyboardBackend()
