"""Headsets, through HeadsetControl: battery, sidetone, auto power-off, lights.

HeadsetControl can only *write* these settings, so RigDeck remembers what was chosen
(`[headset]` in config.toml) and the service re-applies it each time the headset turns on.
"""
from __future__ import annotations

import logging
import os

from ... import config
from ..base import Module, RigdeckError, ServiceTask
from . import hc

log = logging.getLogger("rigdeck.headset")

POLL = 15.0          # seconds between "is the headset on?" checks in the service
SETTINGS = ("sidetone", "inactive_time", "lights", "voice_prompts", "rotate_to_mute")


def saved(cfg: dict | None = None) -> dict:
    """Settings chosen in RigDeck, {capability: int}."""
    table = (cfg if cfg is not None else config.load()).get("headset", {})
    return {k: int(table[k]) for k in SETTINGS if k in table}


def change(settings: dict) -> dict:
    """Apply settings to the headset now and remember them. Returns the headset status."""
    st = hc.status()
    if st is None:
        raise RigdeckError("no supported headset found")
    if not st["on"]:
        raise RigdeckError("the headset is off — turn it on and try again")
    unsupported = [k for k in settings if k not in st["caps"]]
    if unsupported:
        raise RigdeckError(f"{st['name']} doesn't support: {', '.join(unsupported)}")
    hc.apply(st["id"], settings)
    cfg = config.load()
    config.section(cfg, "headset").update({k: int(v) for k, v in settings.items()})
    config.save(cfg)
    return st


class HeadsetTask(ServiceTask):
    """Re-applies the saved settings whenever the headset turns on (it may forget them)."""

    def __init__(self):
        self.was_on = False
        self.settings: dict = {}

    def reload(self, cfg: dict):
        self.settings = saved(cfg)

    def tick(self, now: float) -> float:
        try:
            st = hc.status()
        except hc.NotInstalled:
            return 300.0
        except hc.HeadsetError as e:
            log.debug("headset status failed: %s", e)
            return POLL
        on = bool(st and st["on"])
        if on and not self.was_on and self.settings:
            todo = {k: v for k, v in self.settings.items() if k in st["caps"]}
            try:
                hc.apply(st["id"], todo)
                log.info("%s on: applied %s", st["name"], todo)
            except hc.HeadsetError as e:
                log.warning("%s: could not apply settings: %s", st["name"], e)
                on = False  # retry next time
        self.was_on = on
        return POLL


# ---- CLI ------------------------------------------------------------------------------

def _on_off(v: str) -> int:
    if v in ("on", "1", "true", "yes"):
        return 1
    if v in ("off", "0", "false", "no"):
        return 0
    raise ValueError("use on or off")


def cli_status(a):
    st = hc.status()
    if st is None:
        print("No supported headset found.")
        return
    print(f"{'Headset':<16}{st['name']}  ({st['id']})")
    if not st["on"]:
        print(f"{'Status':<16}off (the receiver is connected, the headset isn't)")
    elif st["battery"] is not None:
        print(f"{'Battery':<16}{st['battery']}%" + (" (charging)" if st["charging"] else ""))
    s = saved()
    labels = {"sidetone": "Sidetone", "inactive_time": "Auto-off", "lights": "Lights",
              "voice_prompts": "Voice prompts", "rotate_to_mute": "Rotate to mute"}
    for k in SETTINGS:
        if k in st["caps"]:
            v = s.get(k)
            if v is None:
                shown = "not set by RigDeck"
            elif k == "inactive_time":
                shown = "never" if v == 0 else f"after {v} min"
            elif k == "sidetone" and not st["sidetone_on_off"]:
                shown = "off" if v == 0 else f"level {v} of 128"
            else:
                shown = "on" if v else "off"
            print(f"{labels[k]:<16}{shown}")


def cli_sidetone(a):
    v = a.level
    level = 128 if v == "on" else 0 if v == "off" else int(v)
    if not 0 <= level <= 128:
        raise ValueError("sidetone is 0–128, on or off")
    change({"sidetone": level})
    print("sidetone " + ("off" if level == 0 else "on" if level in (1, 128) else f"set to {level}"))


def cli_auto_off(a):
    if not 0 <= a.minutes <= 90:
        raise ValueError("auto-off is 0–90 minutes (0 = never)")
    change({"inactive_time": a.minutes})
    print("auto-off: " + ("never" if a.minutes == 0 else f"after {a.minutes} min idle"))


def cli_switch(key, label):
    def run(a):
        change({key: _on_off(a.state)})
        print(f"{label}: {a.state}")
    return run


class HeadsetModule(Module):
    id = "headset"
    title = "Headset"
    icon = "headphones"
    kind = "peripheral"
    order = 60

    def detect(self) -> bool:
        return hc.present()

    def add_cli(self, sub):
        p = sub.add_parser("headset", help="headset: battery, sidetone, auto power-off (via HeadsetControl)")
        hs = p.add_subparsers(dest="headset_cmd", required=True)
        hs.add_parser("status", help="battery and settings").set_defaults(func=cli_status)
        s = hs.add_parser("sidetone", help="hear your own microphone: on, off, or a level 0–128")
        s.add_argument("level")
        s.set_defaults(func=cli_sidetone)
        o = hs.add_parser("auto-off", help="turn off after N idle minutes (0 = never)")
        o.add_argument("minutes", type=int)
        o.set_defaults(func=cli_auto_off)
        for name, key, help_ in (("lights", "lights", "lights"),
                                 ("voice-prompts", "voice_prompts", "spoken status announcements"),
                                 ("rotate-to-mute", "rotate_to_mute", "mute when the mic arm is raised")):
            x = hs.add_parser(name, help=f"{help_}: on or off (if the headset has them)")
            x.add_argument("state", choices=["on", "off"])
            x.set_defaults(func=cli_switch(key, help_.split(":")[0].capitalize()))

    def service_task(self):
        return HeadsetTask() if hc.installed() else None

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "HeadsetPage.qml")

    def qt_backend(self, app):
        from .qt import HeadsetBackend
        return HeadsetBackend()
