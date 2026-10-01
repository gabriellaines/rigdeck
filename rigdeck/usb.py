"""Which USB devices are plugged in, from sysfs (no device is opened)."""
from __future__ import annotations

import glob
import os


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def connected() -> set[tuple[int, int]]:
    """{(vendor_id, product_id)} of every connected USB device."""
    ids = set()
    for dev in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        d = os.path.dirname(dev)
        try:
            ids.add((int(_read(dev), 16), int(_read(os.path.join(d, "idProduct")), 16)))
        except ValueError:
            pass
    return ids


def fmt_id(vid: int, pid: int) -> str:
    return f"{vid:04x}:{pid:04x}"
