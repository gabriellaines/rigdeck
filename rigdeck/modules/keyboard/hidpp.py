"""Minimal HID++ 2.0 client over hidraw, for Logitech devices plugged in by USB.

Messages: short (report 0x10, 7 bytes) and long (0x11, 20 bytes):
    [report, device index (0xFF = the USB device itself), feature index, function << 4 | sw id, params…]
Feature indexes are looked up per device through the root feature (index 0).
Error replies use feature index 0xFF (HID++ 2.0 error) with the error code in byte 5.
"""
from __future__ import annotations

import glob
import os
import select
import time

from ..base import RigdeckError

LOGITECH = 0x046D
LONG, SHORT = 0x11, 0x10
DEVICE = 0xFF
SW_ID = 0x0A   # arbitrary, identifies our replies

ROOT, FEATURE_SET, FW_VERSION, DEVICE_NAME = 0x0000, 0x0001, 0x0003, 0x0005
BRIGHTNESS = 0x8040
ERRORS = {1: "unknown", 2: "invalid argument", 3: "out of range", 4: "hardware error", 5: "Logitech internal",
          6: "invalid feature index", 7: "invalid function", 8: "busy", 9: "unsupported"}


class HidppError(RigdeckError):
    pass


def interfaces(pids) -> list[tuple[str, int]]:
    """[(/dev/hidrawN, pid)] of Logitech HID++ interfaces (long report 0x11 in the descriptor)."""
    out = []
    for sysdir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(sysdir, "device/uevent")).read()
            desc = open(os.path.join(sysdir, "device/report_descriptor"), "rb").read()
        except OSError:
            continue
        hid_id = next((ln.split("=", 1)[1] for ln in uevent.splitlines() if ln.startswith("HID_ID=")), "")
        parts = hid_id.split(":")
        try:
            vid, pid = int(parts[1], 16), int(parts[2], 16)
        except (IndexError, ValueError):
            continue
        if vid == LOGITECH and pid in pids and b"\x85\x11" in desc:
            out.append(("/dev/" + os.path.basename(sysdir), pid))
    return out


class Device:
    def __init__(self, node: str, timeout: float = 1.0):
        self.node, self.timeout = node, timeout
        try:
            self.fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as e:
            raise HidppError(f"no permission to open {node} — RigDeck's device rule isn't installed "
                             "(re-run the installer)") from e
        except OSError as e:
            raise HidppError(f"can't open {node}: {e.strerror}") from e
        self._index: dict[int, int | None] = {ROOT: 0}

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def call(self, index: int, function: int, params: bytes = b"") -> bytes:
        """Send a long request; return the reply's 16 parameter bytes."""
        msg = bytes([LONG, DEVICE, index, (function << 4) | SW_ID]) + params
        os.write(self.fd, msg + bytes(20 - len(msg)))
        end = time.monotonic() + self.timeout
        while time.monotonic() < end:
            if not select.select([self.fd], [], [], 0.05)[0]:
                continue
            try:
                d = os.read(self.fd, 64)
            except BlockingIOError:
                continue
            if len(d) < 5 or d[0] not in (LONG, SHORT):
                continue
            if d[2] == 0xFF and d[3] == index and d[4] == msg[3]:
                raise HidppError(f"keyboard refused the request ({ERRORS.get(d[5], d[5])})")
            if d[2] == index and d[3] == msg[3]:
                return bytes(d[4:]) + bytes(16 - len(d[4:]))
        raise HidppError("the keyboard didn't answer")

    def index(self, feature: int) -> int | None:
        if feature not in self._index:
            r = self.call(0, 0, feature.to_bytes(2, "big"))
            self._index[feature] = r[0] or None
        return self._index[feature]

    def feature(self, feature: int, function: int, params: bytes = b"") -> bytes:
        i = self.index(feature)
        if i is None:
            raise HidppError(f"feature 0x{feature:04x} not supported")
        return self.call(i, function, params)

    # ---- generic features ------------------------------------------------------------

    def features(self) -> list[tuple[int, int, int]]:
        """[(feature id, type flags, version)] — the device's own feature list."""
        n = self.feature(FEATURE_SET, 0)[0]
        out = []
        for i in range(1, n + 1):
            r = self.feature(FEATURE_SET, 1, bytes([i]))
            out.append(((r[0] << 8) | r[1], r[2], r[3]))
        return out

    def name(self) -> str:
        length = self.feature(DEVICE_NAME, 0)[0]
        name = b""
        while len(name) < length:
            name += self.feature(DEVICE_NAME, 1, bytes([len(name)])).rstrip(b"\0")[:16] or b" "
        return name[:length].decode(errors="replace").strip()

    def firmware(self) -> str:
        """Main application firmware, e.g. 'U1 70.04 build 0020'."""
        for e in range(self.feature(FW_VERSION, 0)[0]):
            r = self.feature(FW_VERSION, 1, bytes([e]))
            if r[0] == 0:  # 0 = main application
                return f"{r[1:4].decode(errors='replace').strip(chr(0) + ' ')} {r[4]:02x}.{r[5]:02x} build {r[6]:02x}{r[7]:02x}"
        return ""
