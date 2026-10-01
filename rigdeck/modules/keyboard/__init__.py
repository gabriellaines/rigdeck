"""Logitech G keyboards over HID++ 2.0 (USB): identity and lighting brightness.

Supported: PRO X TKL RAPID (046d:c35b). Its analog settings (actuation point, Rapid Trigger)
use a feature no public project documents yet (0x1b08); until it's decoded, they're set on the
keyboard itself (Fn+F5 custom analog profile), which RigDeck explains on the page.
"""
from __future__ import annotations

import os

from ..base import Module, RigdeckError
from . import hidpp
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

    def detect(self) -> bool:
        return bool(connected())

    def add_cli(self, sub):
        p = sub.add_parser("keyboard", help="Logitech G keyboard: lighting brightness")
        ks = p.add_subparsers(dest="keyboard_cmd", required=True)
        ks.add_parser("status", help="model, firmware, brightness").set_defaults(func=cli_status)
        b = ks.add_parser("brightness", help="lighting brightness in percent (0 = off)")
        b.add_argument("percent", type=int)
        b.set_defaults(func=cli_brightness)
        ks.add_parser("features", help="list the keyboard's HID++ features (for developers)")\
            .set_defaults(func=cli_features)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "KeyboardPage.qml")

    def qt_backend(self, app):
        from .qt import KeyboardBackend
        return KeyboardBackend()
