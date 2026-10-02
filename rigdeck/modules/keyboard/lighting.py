"""Per-key colours of the PRO X TKL RAPID, the way G HUB does them (decoded 2026-10-02).

Software control of the LEDs is claimed through 0x8071 (RGB_EFFECTS) fn 5 and handed back with
fn 5 `01 00 00`; while claimed, the keyboard shows a canvas painted through 0x8081
(PER_KEY_LIGHTING_V2): fn 5 fills ranges `[first, last, R, G, B]` ×3, fn 1 sets single zones
`[zone, R, G, B]` ×4, fn 7 shows the frame. Like the analog settings these are live only, so the
service re-applies them (a profile switch or unplugging brings the onboard lighting back).
"""
from __future__ import annotations

from . import hidpp
from .keymap import KEYS, MEDIA_ZONES, zone

RGB_EFFECTS, PER_KEY = 0x8071, 0x8081
# Every LED zone this keyboard has (what G HUB fills): main block, modifiers, Menu, media keys.
ZONE_RANGES = [(0x01, 0x2E), (0x30, 0x4F), (0x68, 0x6F), (0x62, 0x62), (0x96, 0x96), (0x98, 0x9B)]
LIT_KEYS = [n for n in [*KEYS.values(), *MEDIA_ZONES] if zone(n) is not None]


def parse(color: str) -> bytes:
    c = color.strip().lstrip("#")
    if len(c) != 6:
        raise ValueError(f"colour {color!r} is not rrggbb")
    return bytes.fromhex(c)


def take_control(k: hidpp.Device):
    k.feature(RGB_EFFECTS, 5, b"\x01\x03\x07")
    k.feature(RGB_EFFECTS, 8, b"\x01\x01\x00")
    k.feature(RGB_EFFECTS, 5, b"\x01\x03\x05")
    k.feature(RGB_EFFECTS, 1, bytes([0xFF, 0x01]) + bytes(10) + b"\x01")     # per-key canvas


def release(k: hidpp.Device):
    """Back to the keyboard's own (onboard profile) lighting."""
    k.feature(RGB_EFFECTS, 5, b"\x01\x00\x00")


def paint(k: hidpp.Device, base: str, keys: dict[str, str]):
    """Every LED `base` (rrggbb), then the per-key colours {key name: rrggbb}; shown at once."""
    b = parse(base)
    ranges = [bytes([lo, hi]) + b for lo, hi in ZONE_RANGES]
    for i in range(0, len(ranges), 3):
        k.feature(PER_KEY, 5, b"".join(ranges[i:i + 3]))
    singles = [bytes([zone(n)]) + parse(c) for n, c in keys.items() if zone(n) is not None]
    for i in range(0, len(singles), 4):
        k.feature(PER_KEY, 1, b"".join(singles[i:i + 4]))
    k.feature(PER_KEY, 7, bytes(16))


def apply(k: hidpp.Device, base: str, keys: dict[str, str]):
    take_control(k)
    paint(k, base, keys)
