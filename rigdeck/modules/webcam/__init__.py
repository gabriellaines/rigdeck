"""Webcams (any UVC camera): image, white balance, exposure, focus and zoom controls.

Webcams forget their settings when unplugged or after a reboot, so RigDeck saves what was chosen
per camera (`[webcam.<id>]` in config.toml) and the service re-applies it when the camera appears.
"""
from __future__ import annotations

import logging
import os

from ... import config
from ..base import Module, RigdeckError, ServiceTask
from . import v4l2

log = logging.getLogger("rigdeck.webcam")

POLL = 3.0

# Friendly names, groups and units for well-known UVC controls; anything else shows as-is.
GROUPS = [
    ("Image", ["brightness", "contrast", "saturation", "sharpness", "gain", "gamma", "hue",
               "backlight_compensation"]),
    ("White balance", ["white_balance_automatic", "white_balance_temperature"]),
    ("Exposure", ["auto_exposure", "exposure_time_absolute", "exposure_dynamic_framerate",
                  "power_line_frequency"]),
    ("Focus and framing", ["focus_automatic_continuous", "focus_absolute", "zoom_absolute",
                           "pan_absolute", "tilt_absolute"]),
]
LABELS = {
    "white_balance_automatic": ("Automatic white balance", ""),
    "white_balance_temperature": ("Color temperature", "Lower is warmer (yellow), higher is cooler (blue)"),
    "auto_exposure": ("Exposure", ""),
    "exposure_time_absolute": ("Exposure time", "Longer is brighter but blurs movement"),
    "exposure_dynamic_framerate": ("Lower frame rate in dim light", "Brighter picture, less smooth video"),
    "power_line_frequency": ("Anti-flicker", "Match your mains power: 50 Hz (Europe, most of Asia) or 60 Hz (Americas)"),
    "backlight_compensation": ("Backlight compensation", "Brightens faces against a bright window"),
    "focus_automatic_continuous": ("Autofocus", ""),
    "focus_absolute": ("Focus", "Lower is far, higher is close"),
    "zoom_absolute": ("Zoom", ""),
    "pan_absolute": ("Pan", "Moves the picture left/right when zoomed in"),
    "tilt_absolute": ("Tilt", "Moves the picture up/down when zoomed in"),
    "gain": ("Gain", "Brightens the picture electronically; adds noise"),
}
MENU_LABELS = {"Manual Mode": "Manual", "Aperture Priority Mode": "Automatic", "Auto Mode": "Automatic",
               "Shutter Priority Mode": "Shutter priority"}
UNITS = {"white_balance_temperature": "kelvin", "zoom_absolute": "zoom", "pan_absolute": "degrees",
         "tilt_absolute": "degrees"}


def describe(controls: list[dict]) -> list[dict]:
    """Controls grouped for display: [{title, controls: [{…, label, hint, unit}]}]."""
    by_key = {c["key"]: c for c in controls}
    groups, used = [], set()
    for title, keys in GROUPS + [("Other", [c["key"] for c in controls])]:
        items = []
        for k in keys:
            c = by_key.get(k)
            if c is None or k in used:
                continue
            used.add(k)
            label, hint = LABELS.get(k, (c["name"], ""))
            kind = "bool" if c["type"] == "int" and (c["min"], c["max"]) == (0, 1) else c["type"]
            menu = [{"value": m["value"], "label": MENU_LABELS.get(m["label"], m["label"])}
                    for m in c.get("menu", [])]
            items.append({**c, "type": kind, "menu": menu, "label": label, "hint": hint,
                          "unit": UNITS.get(k, "")})
        if items:
            groups.append({"title": title, "controls": items})
    return groups


def saved(by_id: str, cfg: dict | None = None) -> dict:
    cfg = cfg if cfg is not None else config.load()
    return dict(cfg.get("webcam", {}).get(v4l2.config_key(by_id), {}))


def remember(by_id: str, values: dict | None):
    """Merge values into the saved settings for this camera (None = forget them all)."""
    cfg = config.load()
    table = config.section(cfg, "webcam")
    key = v4l2.config_key(by_id)
    if values is None:
        table.pop(key, None)
    else:
        table.setdefault(key, {}).update({k: int(v) for k, v in values.items()})
    config.save(cfg)


def change(by_id: str, values: dict) -> list[str]:
    with v4l2.Camera(by_id) as cam:
        failed = cam.apply(values)
    remember(by_id, {k: v for k, v in values.items() if k not in failed})
    return failed


def reset(by_id: str):
    """Back to the camera's defaults, and forget the saved settings."""
    with v4l2.Camera(by_id) as cam:
        cam.apply({c["key"]: c["default"] for c in cam.controls()})
    remember(by_id, None)


class WebcamTask(ServiceTask):
    """Re-applies saved settings to each camera when it appears (plugged in, after boot)."""

    def __init__(self):
        self.present: set[str] = set()
        self.cfg: dict = {}

    def reload(self, cfg: dict):
        self.cfg = cfg

    def tick(self, now: float) -> float:
        current = set(v4l2.cameras())
        for by_id in sorted(current - self.present):
            values = saved(by_id, self.cfg)
            if not values:
                continue
            try:
                with v4l2.Camera(by_id) as cam:
                    failed = cam.apply(values)
                log.info("%s: applied %d saved settings%s", cam.name, len(values) - len(failed),
                         f" ({', '.join(failed)} not supported)" if failed else "")
            except (v4l2.WebcamError, OSError) as e:
                log.warning("%s: could not apply settings: %s", by_id, e)
                current.discard(by_id)  # try again next tick
        self.present = current
        return POLL


# ---- CLI ------------------------------------------------------------------------------

def _pick(n: int | None) -> str:
    cams = v4l2.cameras()
    if not cams:
        raise RigdeckError("no webcam found")
    if n is None:
        return cams[0]
    if not 0 <= n < len(cams):
        raise RigdeckError(f"there are {len(cams)} webcams; use --camera 0…{len(cams) - 1}")
    return cams[n]


def _shown(c: dict) -> str:
    if c["type"] in ("menu", "intmenu"):
        return next((m["label"] for m in c["menu"] if m["value"] == c["value"]), str(c["value"]))
    if c["type"] == "bool":
        return "on" if c["value"] else "off"
    return str(c["value"])


def cli_list(a):
    for i, by_id in enumerate(v4l2.cameras()):
        with v4l2.Camera(by_id) as cam:
            print(f"{i}  {cam.name}  ({cam.path}, {by_id})")


def cli_status(a):
    by_id = _pick(a.camera)
    with v4l2.Camera(by_id) as cam:
        print(f"{cam.name}  ({cam.path})")
        groups = describe(cam.controls())
    remembered = saved(by_id)
    for g in groups:
        print(f"\n{g['title']}")
        for c in g["controls"]:
            rng = f"{c['min']}–{c['max']}" if c["type"] == "int" else \
                  " / ".join(m["label"] for m in c["menu"]) if c["menu"] else "on / off"
            flags = (" (inactive)" if c["inactive"] else "") + (" *" if c["key"] in remembered else "")
            print(f"  {c['key']:<30}{_shown(c):<12}{rng}{flags}")
    print("\n* saved by RigDeck and re-applied when the camera is plugged in")


def cli_set(a):
    by_id = _pick(a.camera)
    values = {}
    for item in a.values:
        k, _, v = item.partition("=")
        if not v:
            raise ValueError(f"use KEY=VALUE, e.g. brightness=140 (got {item!r})")
        values[k.strip()] = {"on": 1, "off": 0}.get(v.strip().lower(), v.strip())
    try:
        values = {k: int(v) for k, v in values.items()}
    except ValueError:
        raise ValueError("values are numbers (or on/off); see `rigdeck webcam status`")
    failed = change(by_id, values)
    if failed:
        raise RigdeckError(f"not set: {', '.join(failed)} (unknown or inactive — see `rigdeck webcam status`)")
    print("applied and saved")


def cli_reset(a):
    reset(_pick(a.camera))
    print("camera back to its defaults; saved settings removed")


class WebcamModule(Module):
    id = "webcam"
    title = "Webcam"
    icon = "webcam"
    kind = "peripheral"
    order = 70

    def detect(self) -> bool:
        return bool(v4l2.cameras())

    def add_cli(self, sub):
        p = sub.add_parser("webcam", help="webcam image, exposure, focus and zoom")
        ws = p.add_subparsers(dest="webcam_cmd", required=True)
        ws.add_parser("list", help="connected webcams").set_defaults(func=cli_list)
        for name, fn, help_ in (("status", cli_status, "controls and their values"),
                                ("reset", cli_reset, "back to the camera's defaults")):
            x = ws.add_parser(name, help=help_)
            x.add_argument("--camera", type=int, metavar="N", help="which webcam (see `list`), default the first")
            x.set_defaults(func=fn)
        s = ws.add_parser("set", help="change controls, e.g. brightness=140 focus_automatic_continuous=off")
        s.add_argument("values", nargs="+", metavar="KEY=VALUE")
        s.add_argument("--camera", type=int, metavar="N")
        s.set_defaults(func=cli_set)

    def service_task(self):
        return WebcamTask()

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "WebcamPage.qml")

    def qt_backend(self, app):
        from .qt import WebcamBackend
        return WebcamBackend()
