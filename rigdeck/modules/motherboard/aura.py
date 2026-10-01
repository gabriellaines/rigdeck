"""ASUS Aura USB motherboard lighting controller (0b05:18f3/1939/19af/1aa6/1bed).

Protocol as implemented by OpenRGB (Controllers/AsusAuraUSBController, GPL-2.0-or-later):
65-byte HID reports starting with 0xEC.
    0x82            firmware version   -> reply ec 02 "AULA3-AR42-0222"
    0xB0            config table       -> reply ec 30 .. table at bytes 4..63
                                          [0x02] ARGB headers, [0x1B] fixed LEDs (incl. RGB headers), [0x1D] RGB headers
    0x52 53 00 01   select the effect protocol (OpenRGB sends it once on open)
    0x35 ch 00 sd m effect m on effect channel ch (0 = board LEDs, 1.. = ARGB headers); sd = shutdown effect
    0x36 mh ml sd … effect colors: 16-bit LED mask, then RGB triplets at 5 + 3*led
    0x3F 55         commit: keep the settings after a restart
The controller can't report its current effect or color.
"""
from __future__ import annotations

import glob
import os
import select
import time

from ..base import RigdeckError

VENDOR = 0x0B05
PIDS = {0x18F3, 0x1939, 0x19AF, 0x1AA6, 0x1BED}
MODES = {"off": 0, "static": 1, "breathing": 2, "flashing": 3, "cycle": 4, "rainbow": 5}


class AuraError(RigdeckError):
    pass


def find() -> str | None:
    for sysdir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(sysdir, "device/uevent")).read()
        except OSError:
            continue
        hid_id = next((ln.split("=", 1)[1] for ln in uevent.splitlines() if ln.startswith("HID_ID=")), "")
        parts = hid_id.split(":")
        try:
            if int(parts[1], 16) == VENDOR and int(parts[2], 16) in PIDS:
                return "/dev/" + os.path.basename(sysdir)
        except (IndexError, ValueError):
            continue
    return None


def zones_from_table(table: bytes) -> list[dict]:
    """Lighting zones the board has, from the config table (as OpenRGB interprets it)."""
    fixed, rgb_headers, argb = table[0x1B], table[0x1D], table[0x02]
    if fixed < rgb_headers:
        rgb_headers = 0
    zones = []
    if fixed:
        zones.append({"id": "board", "channel": 0, "first": 0, "leds": fixed, "rgbHeaders": rgb_headers,
                      "label": "Board" + (f" and {rgb_headers} RGB header{'s' if rgb_headers > 1 else ''}"
                                          if rgb_headers else "")})
    for i in range(argb):
        zones.append({"id": f"argb{i + 1}", "channel": len(zones), "first": fixed + i, "leds": 1, "rgbHeaders": 0,
                      "label": f"ARGB header {i + 1}" if argb > 1 else "ARGB header"})
    return zones


class Aura:
    def __init__(self, node: str):
        self.node = node
        try:
            self.fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as e:
            raise AuraError(f"no permission to open {node} — RigDeck's device rule isn't installed "
                            "(re-run the installer)") from e
        except OSError as e:
            raise AuraError(f"can't open {node}: {e.strerror}") from e

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _send(self, *data: int):
        os.write(self.fd, bytes([0xEC, *data]) + bytes(64 - len(data)))

    def _ask(self, cmd: int, reply_id: int) -> bytes:
        while select.select([self.fd], [], [], 0)[0]:   # drop stale reports
            os.read(self.fd, 65)
        self._send(cmd)
        end = time.monotonic() + 1
        while time.monotonic() < end:
            if select.select([self.fd], [], [], 0.05)[0]:
                r = os.read(self.fd, 65)
                if len(r) > 2 and r[0] == 0xEC and r[1] == reply_id:
                    return r
        raise AuraError("the lighting controller didn't answer")

    def firmware(self) -> str:
        return self._ask(0x82, 0x02)[2:18].split(b"\0")[0].decode(errors="replace")

    def zones(self) -> list[dict]:
        return zones_from_table(self._ask(0xB0, 0x30)[4:64])

    def set(self, zone: dict, mode: str, rgb: tuple[int, int, int], keep: bool = True):
        """Effect + color for one zone; keep=True also stores it in the controller (survives restarts)."""
        if mode not in MODES:
            raise AuraError(f"effect must be one of {', '.join(MODES)}")
        self._send(0x52, 0x53, 0x00, 0x01)
        self._send(0x35, zone["channel"], 0x00, 0x00, MODES[mode])
        if mode != "off":
            mask = ((1 << zone["leds"]) - 1) << zone["first"]
            colors = bytearray(60)
            for i in range(zone["leds"]):
                colors[3 * (zone["first"] + i):3 * (zone["first"] + i) + 3] = bytes(rgb)
            self._send(0x36, mask >> 8, mask & 0xFF, 0x00, *colors[:60])
        if keep:
            self._send(0x3F, 0x55)
