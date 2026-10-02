"""Bluetooth adapters and devices from BlueZ (the system Bluetooth service), over D-Bus via busctl.

Pairing and connecting stay in the desktop's own settings; RigDeck shows what's connected, battery
levels, and can switch an adapter on or off. Devices are sorted into categories from BlueZ's
device-type icon, so a Bluetooth headset shows on the Headset page, a mouse on the Mouse page…
"""
from __future__ import annotations

import json
import shutil
import subprocess

# BlueZ Device1.Icon -> RigDeck category (pages: headset, mouse, keyboard; the rest: Bluetooth page)
CATEGORIES = {"audio-headset": "headset", "audio-headphones": "headset", "audio-card": "audio",
              "input-mouse": "mouse", "input-keyboard": "keyboard", "input-gaming": "controller",
              "input-tablet": "tablet", "phone": "phone", "computer": "computer"}
LABELS = {"headset": "Headphones", "audio": "Speaker", "mouse": "Mouse", "keyboard": "Keyboard",
          "controller": "Controller", "tablet": "Tablet", "phone": "Phone", "computer": "Computer",
          "other": "Device"}
ICONS = {"headset": "headphones", "mouse": "mouse", "keyboard": "keyboard"}   # Lucide; else "bluetooth"


def parse(data: dict) -> tuple[list[dict], list[dict]]:
    """(adapters, devices) from GetManagedObjects; only your paired or connected devices."""
    adapters, devices = [], []
    for path, ifaces in data.items():
        def props(name):
            return {k: v["data"] for k, v in ifaces.get(name, {}).items()}
        if "org.bluez.Adapter1" in ifaces:
            a = props("org.bluez.Adapter1")
            adapters.append({"path": path, "name": a.get("Alias") or a.get("Name", ""),
                             "address": a.get("Address", ""), "powered": bool(a.get("Powered"))})
        if "org.bluez.Device1" in ifaces:
            d = props("org.bluez.Device1")
            if not d.get("Paired") and not d.get("Connected"):
                continue   # seen nearby, not yours
            cat = CATEGORIES.get(d.get("Icon", ""), "other")
            devices.append({"path": path, "name": d.get("Alias") or d.get("Name") or d.get("Address", ""),
                            "address": d.get("Address", ""), "category": cat, "kind": LABELS[cat],
                            "icon": ICONS.get(cat, "bluetooth"), "connected": bool(d.get("Connected")),
                            "battery": props("org.bluez.Battery1").get("Percentage"),
                            "adapter": d.get("Adapter", "")})
    devices.sort(key=lambda d: (not d["connected"], d["name"].lower()))
    return adapters, devices


def read() -> tuple[list[dict], list[dict]]:
    """([], []) when BlueZ isn't running or there's no adapter."""
    if not shutil.which("busctl"):
        return [], []
    try:
        r = subprocess.run(["busctl", "--system", "--json=short", "call", "org.bluez", "/",
                            "org.freedesktop.DBus.ObjectManager", "GetManagedObjects"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return [], []
        return parse(json.loads(r.stdout)["data"][0])
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, IndexError):
        return [], []


def set_powered(adapter_path: str, on: bool):
    from .modules.base import RigdeckError
    r = subprocess.run(["busctl", "--system", "set-property", "org.bluez", adapter_path, "org.bluez.Adapter1",
                        "Powered", "b", "true" if on else "false"], capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RigdeckError((r.stderr or "busctl failed").strip())


def settings_command(page: str) -> list[str] | None:
    """The desktop's own settings page for 'bluetooth' or 'network', if we know how to open it."""
    if shutil.which("systemsettings"):
        return ["systemsettings", {"bluetooth": "kcm_bluetooth", "network": "kcm_networkmanagement"}[page]]
    if shutil.which("gnome-control-center"):
        return ["gnome-control-center", {"bluetooth": "bluetooth", "network": "wifi"}[page]]
    return None
