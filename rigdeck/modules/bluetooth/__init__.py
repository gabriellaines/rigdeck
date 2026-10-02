"""Bluetooth: adapters and your devices (from BlueZ). The page appears in the sidebar only while a
Bluetooth device is connected; pairing and connecting stay in the desktop's own settings."""
from __future__ import annotations

import os

from ... import bluez
from ..base import Module


def cli_status(a):
    adapters, devices = bluez.read()
    if not adapters:
        print("No Bluetooth adapter (or the Bluetooth service isn't running)")
        return
    for ad in adapters:
        print(f"{ad['path'].rsplit('/', 1)[-1]}  {'on' if ad['powered'] else 'off'}  as \"{ad['name']}\"  {ad['address']}")
    if not devices:
        print("  no paired devices")
    for d in devices:
        bat = f"  {d['battery']}% battery" if d["battery"] is not None else ""
        print(f"  {d['name']:<32}{d['kind']:<12}{'connected' if d['connected'] else 'paired'}{bat}")


class BluetoothModule(Module):
    id = "bluetooth"
    title = "Bluetooth"
    icon = "bluetooth"
    kind = "system"
    order = 56
    bluetooth = ("*",)       # shown only while some Bluetooth device is connected

    def detect(self) -> bool:
        return False         # never shown just because an adapter exists

    def add_cli(self, sub):
        sub.add_parser("bluetooth", help="Bluetooth adapters and your devices").set_defaults(func=cli_status)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "BluetoothPage.qml")
