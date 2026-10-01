"""Low-level driver for GIGABYTE AORUS WATERFORCE X II AIO coolers (USB 0414:7a5e).

Protocol reverse-engineered from GIGABYTE Control Center 26.08 (see PROTOCOL.md).
Every report uses HID report ID 0x99; output reports are 6144 bytes, input reports 256.
"""
from __future__ import annotations

import errno
import glob
import os
import select
import time
from dataclasses import dataclass
from enum import IntEnum

from ..base import RigdeckError

VENDOR_ID = 0x0414
PRODUCT_IDS = {0x7A5E: "AORUS WATERFORCE X II"}

REPORT_ID = 0x99
OUT_LEN = 6144
IN_LEN = 256
CHUNK = OUT_LEN - 3  # upload payload per 0xF2 report


class SpeedType(IntEnum):
    FAN = 1
    PUMP = 2


class SpeedMode(IntEnum):
    BALANCED = 0
    CUSTOMIZED = 1
    DEFAULT = 2
    FIXED_RPM = 3
    TURBO = 4
    PERFORMANCE = 5
    QUIET = 6
    ZERO_RPM = 7


FAN_MODES = [SpeedMode.DEFAULT, SpeedMode.ZERO_RPM, SpeedMode.QUIET, SpeedMode.BALANCED,
             SpeedMode.PERFORMANCE, SpeedMode.TURBO, SpeedMode.CUSTOMIZED]
PUMP_MODES = [SpeedMode.BALANCED, SpeedMode.TURBO]

# Preset curves GCC shows for the X II series (points at 0/30/50/65 °C). Zero RPM has none published.
PRESET_TEMPS = (0, 30, 50, 65)
PRESET_FAN = {
    SpeedMode.DEFAULT: (1200, 1200, 1400, 2000),
    SpeedMode.QUIET: (1000, 1000, 1000, 1500),
    SpeedMode.BALANCED: (1200, 1200, 1400, 1800),
    SpeedMode.PERFORMANCE: (1800, 1800, 1800, 2400),
    SpeedMode.TURBO: (2300, 2300, 2300, 2400),
}
PRESET_PUMP = {
    SpeedMode.BALANCED: (2500, 2500, 2500, 3000),
    SpeedMode.TURBO: (3000, 3000, 3000, 3000),
}


def preset_curve(kind: "SpeedType", mode: "SpeedMode") -> list[tuple[int, int]] | None:
    table = PRESET_FAN if kind == SpeedType.FAN else PRESET_PUMP
    rpms = table.get(mode)
    return list(zip(PRESET_TEMPS, rpms)) if rpms else None


MODEL_VARIANTS = {0: "WATERFORCE X II 240", 1: "WATERFORCE X II 360I", 2: "WATERFORCE X II 360"}

# Hardware LED effects; byte layouts replayed exactly as GCC sends them.
LED_STATIC = bytes([0xC9, 0x01, 0x64, 0x0A, 0xCC])
LED_RAINBOW_WAVE = bytes([0xC9, 0x08, 0x64, 0x09, 0xCC, 0xCC])

# Screen modes as reported by 0xE8 / set by 0xE7 (value on the wire).
SCREEN_MODE_CUSTOM_GIF = 7
MAX_CAROUSEL = 250


class CoolerError(RigdeckError):
    pass


@dataclass
class Status:
    fan_rpm: int
    pump_rpm: int
    fan_mode: SpeedMode
    pump_mode: SpeedMode


def find_hidraw() -> list[tuple[str, int]]:
    """Return [(devnode, product_id)] for every supported cooler."""
    found = []
    for sysdir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            with open(os.path.join(sysdir, "device", "uevent")) as f:
                uevent = dict(line.strip().split("=", 1) for line in f if "=" in line)
        except OSError:
            continue
        hid_id = uevent.get("HID_ID", "")  # e.g. 0003:00000414:00007A5E
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        vid, pid = int(parts[1], 16), int(parts[2], 16)
        if vid == VENDOR_ID and pid in PRODUCT_IDS:
            found.append(("/dev/" + os.path.basename(sysdir), pid))
    return found


class Cooler:
    def __init__(self, path: str | None = None):
        if path is None:
            devs = find_hidraw()
            if not devs:
                raise CoolerError("no AORUS WATERFORCE X II found (is it passed through to a VM?)")
            path, self.product_id = devs[0]
        else:
            self.product_id = 0x7A5E
        self.path = path
        try:
            self.fd = os.open(path, os.O_RDWR)
        except PermissionError as e:
            raise CoolerError(f"no permission for {path}; install the rigdeck udev rule (see README)") from e

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ---- transport -------------------------------------------------------

    def _drain(self):
        while select.select([self.fd], [], [], 0)[0]:
            try:
                os.read(self.fd, IN_LEN)
            except BlockingIOError:
                break

    def send(self, payload: bytes):
        """Send one report. `payload` excludes the 0x99 report ID."""
        if len(payload) > OUT_LEN - 1:
            raise ValueError("payload too long")
        buf = bytes([REPORT_ID]) + payload + bytes(OUT_LEN - 1 - len(payload))
        try:
            os.write(self.fd, buf)
        except OSError as e:
            raise CoolerError(f"write failed: {e}") from e

    def query(self, payload: bytes, timeout: float = 1.0, match: int = 1) -> bytes:
        """Send a command and return the 256-byte reply that echoes its first `match` bytes."""
        self._drain()
        self.send(payload)
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            if not select.select([self.fd], [], [], left)[0]:
                break
            try:
                reply = os.read(self.fd, IN_LEN)
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    continue
                raise CoolerError(f"read failed: {e}") from e
            if reply[:1] == bytes([REPORT_ID]) and reply[1:1 + match] == payload[:match]:
                return reply
        raise CoolerError(f"no reply to command 0x{payload[0]:02x}")

    # ---- info ------------------------------------------------------------

    def firmware(self) -> str:
        r = self.query(b"\xd6")
        return f"{r[2]}.{r[3]}"

    def model(self) -> str:
        r = self.query(b"\xde")
        return "GP-AORUS " + MODEL_VARIANTS.get(r[2], f"WATERFORCE X II (variant {r[2]})")

    def rpm(self) -> tuple[int, int]:
        r = self.query(b"\xda")
        return int.from_bytes(r[2:5], "little"), int.from_bytes(r[5:8], "little")

    def modes(self) -> tuple[SpeedMode, SpeedMode]:
        r = self.query(b"\xdd")
        fan, pump = (0 if v == 3 else v for v in r[2:4])
        return SpeedMode(fan), SpeedMode(pump)

    def status(self) -> Status:
        fan_rpm, pump_rpm = self.rpm()
        fan_mode, pump_mode = self.modes()
        return Status(fan_rpm, pump_rpm, fan_mode, pump_mode)

    def curve(self, kind: SpeedType) -> list[tuple[int, int]]:
        r = self.query(bytes([0xD9, kind]))
        return [(r[4 + i * 3], (r[5 + i * 3] << 8) | r[6 + i * 3]) for i in range(4)]

    def storage_free_kb(self) -> int:
        r = self.query(b"\xfa\x42")
        return int.from_bytes(r[3:3 + r[2]], "little")

    def screen_mode(self) -> int:
        return self.query(b"\xe8")[2]

    # ---- cooling ---------------------------------------------------------

    def save(self):
        """Persist current settings to the cooler's flash (GCC does this after every Apply)."""
        self.send(b"\xb6")

    def set_modes(self, fan: SpeedMode, pump: SpeedMode, fan_curve: list[tuple[int, int]] | None = None):
        if pump not in PUMP_MODES:
            raise ValueError(f"pump supports only {[m.name.lower() for m in PUMP_MODES]}")
        self.send(bytes([0xE5, SpeedType.FAN, fan]))
        self.send(bytes([0xE5, SpeedType.PUMP, pump]))
        if fan == SpeedMode.CUSTOMIZED:
            if fan_curve is None:
                raise ValueError("customized mode needs a curve")
            self.set_curve(SpeedType.FAN, fan_curve)
        self.save()

    def set_curve(self, kind: SpeedType, points: list[tuple[int, int]]):
        if len(points) != 4:
            raise ValueError("curve needs exactly 4 (temp °C, rpm) points")
        temps = [t for t, _ in points]
        if temps != sorted(temps) or not all(0 <= t <= 100 for t in temps):
            raise ValueError("curve temperatures must be ascending, 0-100 °C")
        if not all(0 <= s <= 3200 for _, s in points):
            raise ValueError("curve speeds must be 0-3200 rpm")
        buf = bytearray([0xE6, 0x00, kind])
        for t, s in points:
            buf += bytes([t, s >> 8, s & 0xFF])
        self.send(bytes(buf))

    def send_sensors(self, cpu_temp: int, cpu_load: int, ghz_tenths: int = 0,
                     threads: int = 0, cores: int = 0, liquid_temp: int = 0, cpu_power: int = 0,
                     amd: bool = True):
        """Live data the cooler's curves and screen use. Send every ~1.5 s."""
        clamp = lambda v: max(0, min(255, int(v)))
        p = max(0, min(65535, int(cpu_power)))
        self.send(bytes([0xE0, 0 if amd else 1, clamp(cpu_temp), clamp(threads),
                         clamp(ghz_tenths // 10), clamp(ghz_tenths % 10), clamp(cores), 0,
                         clamp(liquid_temp), clamp(cpu_load), p & 0xFF, p >> 8]))

    def send_cpu_name(self, name: str):
        b = name.encode("ascii", "replace")[:250]
        self.send(bytes([0xE1, len(b)]) + b)

    # ---- LEDs ------------------------------------------------------------

    def led_static(self, r: int, g: int, b: int, brightness: int = 100):
        """Solid colour. Brightness (0-100) is applied here, like GCC does."""
        k = max(0, min(100, brightness)) / 100
        self.send(LED_STATIC)
        self.led_color(round(r * k), round(g * k), round(b * k))

    def led_color(self, r: int, g: int, b: int):
        """Change the colour shown in static mode (used for software effects too)."""
        self.send(bytes([0xCD, r & 0xFF, g & 0xFF, b & 0xFF]))

    def led_rainbow_wave(self):
        self.send(LED_RAINBOW_WAVE)

    def led_off(self):
        self.send(LED_STATIC)
        self.led_color(0, 0, 0)

    # ---- screen ----------------------------------------------------------

    def set_rotation(self, degrees: int):
        if degrees % 90:
            raise ValueError("rotation must be 0, 90, 180 or 270")
        self.send(bytes([0xCE, (degrees % 360) // 30]))

    def rotation(self) -> int:
        return self.query(b"\xff")[2] * 30

    def temp_unit_fahrenheit(self) -> bool:
        return self.query(b"\xad")[2] == 1

    def set_temp_unit(self, fahrenheit: bool):
        self.send(bytes([0xAC, 1 if fahrenheit else 0]))

    def upload_media(self, data: bytes, name: str, progress=None, commit_mode: int = 2):
        """Upload an already-converted file (320x320 H.264 MKV) to the cooler's storage."""
        name_b = name.encode("utf-8")
        if len(name_b) > 64:
            raise ValueError("file name too long (max 64 bytes UTF-8)")
        size = len(data).to_bytes(4, "big")
        self.send(bytes([0xF1, 0x01]) + size + bytes([len(name_b) + 1]) + name_b)
        time.sleep(0.01)
        for off in range(0, len(data), CHUNK):
            part = data[off:off + CHUNK]
            marker = 0xFD if len(part) == CHUNK else len(part) & 0xFF
            self.send(bytes([0xF2, marker]) + part)
            time.sleep(0.001)
            if progress:
                progress(min(off + CHUNK, len(data)), len(data))
        self.send(bytes([0xF1, commit_mode]) + size)

    def carousel(self) -> tuple[list[int], int]:
        """(indexes of stored files the screen rotates through, seconds per file)."""
        r = self.query(bytes([0xFD, SCREEN_MODE_CUSTOM_GIF]), match=2)
        playing = []
        for b in r[4:]:
            if not b:
                break
            playing.append(b - 1)
        return playing, r[3]

    def file_ids(self) -> tuple[list[str], dict[str, int]]:
        """(files in current play order, stable ID of each file — 1-based, upload order).

        The listing comes back in *play order*, but the order command takes these fixed IDs.
        Sending the identity order makes the listing show ID order; then the order is put back.
        """
        current = self.list_media()
        n = len(current)
        self.send(bytes([0xF0, SCREEN_MODE_CUSTOM_GIF]) + bytes(range(1, n + 1)))
        time.sleep(0.3)
        by_id = self.list_media()
        ids = {name: i + 1 for i, name in enumerate(by_id)}
        if sorted(by_id) == sorted(current) and len(ids) == n:
            self.send(bytes([0xF0, SCREEN_MODE_CUSTOM_GIF]) + bytes(ids[name] for name in current))
            time.sleep(0.3)
        return current, ids

    def set_carousel(self, order_ids: list[int], playing: list[int], interval: int):
        """Write the screen carousel and save it.

        order_ids: every stored file's ID (see file_ids) in the order they should play.
        playing:   which positions (0-based) of that order are switched on.
        """
        if sorted(order_ids) != list(range(1, len(order_ids) + 1)):
            raise ValueError("order must contain every file ID exactly once")
        positions = sorted(set(playing))
        if not positions:
            raise ValueError("pick at least one file to show")
        if positions[0] < 0 or positions[-1] >= len(order_ids):
            raise ValueError("position out of range")
        interval = max(1, min(255, int(interval)))
        # Same sequence as GCC: order (by ID), then which positions play, then save.
        self.send(bytes([0xF0, SCREEN_MODE_CUSTOM_GIF]) + bytes(order_ids))
        time.sleep(0.3)
        self.send(bytes([0xF6, SCREEN_MODE_CUSTOM_GIF, interval]) + bytes(p + 1 for p in positions))
        time.sleep(0.1)
        self.save()

    def delete_media(self, name: str):
        """Delete a stored animation (path format from GCC: B:/<name>)."""
        path = f"B:/{name}".encode("utf-8")
        self.send(bytes([0xFE, len(path)]) + path)

    def list_media(self) -> list[str]:
        """Names of the GIF/video files stored on the cooler (GCC's 'Carousel List')."""
        self.send(b"\xf3\x02")
        time.sleep(0.5)
        count = self.query(b"\xf4\x02")[3]
        names = []
        for i in range(count):
            r = self.query(bytes([0xF5, 0x02, i]), match=3)
            names.append(r[6:].split(b"\0", 1)[0].decode("utf-8", "replace"))
        return names
