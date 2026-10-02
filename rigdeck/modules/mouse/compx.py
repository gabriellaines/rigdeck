"""Protocol of Compx-based wireless mice (USB vendor 3554): Attack Shark X11 Ultra, Pulsar Xlite V3…

Sources: MontyMcK/attack-shark-x11-ultra-linux PROTOCOL.md (MIT; verified on an X11 Ultra) and the
Linux `hid-pulsar` driver (battery; Pulsar 3554:f507/f508/f509).

Transport: HID report ID 8 on a vendor interface, 16-byte packets both ways:
    [0] command  [1] status  [2..3] flash address (big-endian)  [4] length  [5..14] data  [15] checksum
checksum = 0x55 - sum(report ID + bytes 0..14). Replies echo the request's first bytes. The radio is
busy with motion reports, so requests are re-sent until a matching reply arrives.

Settings live in the mouse's flash (written immediately, kept when unplugged). Single-byte
settings are stored as [value, 0x55 - value]; DPI stages as 4-byte records with their own checksum.
"""
from __future__ import annotations

import glob
import os
import random
import select
import time

from ..base import RigdeckError

VENDOR = 0x3554
REPORT_ID = 8

CMD_HANDSHAKE, CMD_DRIVER, CMD_ONLINE, CMD_BATTERY = 1, 2, 3, 4
CMD_WRITE_FLASH, CMD_READ_FLASH = 7, 8

# Flash offsets (mouse settings region; see PROTOCOL.md "Mouse EEPROM map")
OFF_RATE, OFF_STAGES, OFF_CURRENT_STAGE, OFF_LOD = 0, 2, 4, 10
OFF_DPI, OFF_DPI_COLOR = 12, 44
OFF_LED_MODE, OFF_LED_BRIGHTNESS, OFF_LED_SPEED, OFF_LED_STATE = 76, 78, 80, 82
OFF_DEBOUNCE, OFF_MOTION_SYNC, OFF_SLEEP, OFF_ANGLE_SNAP, OFF_RIPPLE = 169, 171, 173, 175, 177
# Sensor settings of the X11 Ultra (from the vendor's web configurator, all [v, 0x55-v] pairs):
OFF_PERF_STATE, OFF_PERF_TIME, OFF_SENSOR_MODE = 181, 183, 185      # competitive mode on/off, its timer, LP/HP
OFF_ANGLE_TUNE, OFF_ANGLE_TUNE_STATE, OFF_FPS20K = 189, 191, 225     # rotation (signed, +256), on/off, 20K FPS
SETTINGS_SIZE = 256  # everything above lives below this; read it all for a backup

RATE_CODES = {125: 0x08, 250: 0x04, 500: 0x02, 1000: 0x01, 2000: 0x10, 4000: 0x20, 8000: 0x40}
RATES = {v: k for k, v in RATE_CODES.items()}
LED_BRIGHTNESS = [16, 30, 60, 90, 128, 150, 180, 210, 230, 255]   # levels 1..10 as stored


class MouseError(RigdeckError):
    pass


# ---- codecs (pure functions; tested against bytes read from real mice) ----------------

def checksum(body15: bytes) -> int:
    return (0x55 - REPORT_ID - sum(body15)) & 0xFF


def packet(cmd: int, data: bytes = b"", addr: int | None = None, length: int | None = None) -> bytes:
    p = bytearray(16)
    p[0] = cmd
    if addr is not None:
        p[2], p[3] = (addr >> 8) & 0xFF, addr & 0xFF
    p[4] = len(data) if length is None else length
    p[5:5 + len(data)] = data
    p[15] = checksum(bytes(p[:15]))
    return bytes(p)


def pair(value: int) -> bytes:
    return bytes([value & 0xFF, (0x55 - value) & 0xFF])


def unpair(b: bytes) -> int | None:
    """Value of a [v, 0x55-v] pair, or None if the pair doesn't check out."""
    return b[0] if len(b) >= 2 and (b[0] + b[1]) & 0xFF == 0x55 else None


def dpi_record(dpi: int, step: int = 50, simple_max: int = 30000, dpi_max: int = 60000) -> bytes:
    """4-byte DPI stage record. Above `simple_max` the value is stored halved, flagged in byte 2."""
    if not step <= dpi <= dpi_max:
        raise ValueError(f"DPI must be {step}–{dpi_max}")
    if dpi <= simple_max:
        if dpi % step:
            raise ValueError(f"DPI must be a multiple of {step}")
        val, ex = dpi // step - 1, 0
    else:
        if dpi % (step * 2):
            raise ValueError(f"DPI above {simple_max} must be a multiple of {step * 2}")
        val, ex = dpi // 2 // step - 1, 17
    hi = val >> 8
    r = [val & 0xFF, val & 0xFF, ((hi << 2) | (hi << 6) | ex | (ex << 4)) & 0xFF]
    return bytes(r + [(0x55 - sum(r)) & 0xFF])


def dpi_value(r: bytes, step: int = 50) -> int | None:
    if len(r) < 4 or r[3] != (0x55 - sum(r[:3])) & 0xFF:
        return None
    dpi = ((((r[2] >> 2) & 3) << 8 | r[0]) + 1) * step
    return dpi * 2 if r[2] & 1 else dpi


def color_record(rgb: tuple[int, int, int]) -> bytes:
    return bytes([*rgb, (0x55 - sum(rgb)) & 0xFF])


def color_value(r: bytes) -> tuple[int, int, int] | None:
    return tuple(r[:3]) if len(r) >= 4 and r[3] == (0x55 - sum(r[:3])) & 0xFF else None


# ---- finding the configuration interface ---------------------------------------------

def _hid_id(sysdir: str) -> tuple[int, int] | None:
    try:
        uevent = open(os.path.join(sysdir, "device/uevent")).read()
    except OSError:
        return None
    for line in uevent.splitlines():
        if line.startswith("HID_ID="):
            parts = line.split("=", 1)[1].split(":")
            try:
                return int(parts[1], 16), int(parts[2], 16)
            except (IndexError, ValueError):
                return None
    return None


def config_nodes(pids) -> list[tuple[str, int]]:
    """[(/dev/hidrawN, pid)] of interfaces with report ID 8 on a vendor usage page."""
    out = []
    for sysdir in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        ids = _hid_id(sysdir)
        if not ids or ids[0] != VENDOR or ids[1] not in pids:
            continue
        try:
            desc = open(os.path.join(sysdir, "device/report_descriptor"), "rb").read()
        except OSError:
            continue
        vendor_page = any(desc[i] == 0x06 and desc[i + 2] == 0xFF for i in range(len(desc) - 2))
        if vendor_page and b"\x85\x08" in desc:
            out.append(("/dev/" + os.path.basename(sysdir), ids[1]))
    return out


# ---- talking to a mouse ----------------------------------------------------------------

class Mouse:
    """An open configuration interface. Use as a context manager."""

    def __init__(self, node: str, tries: int = 6, window: float = 0.25):
        self.node, self.tries, self.window = node, tries, window
        try:
            self.fd = os.open(node, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as e:
            raise MouseError(f"no permission to open {node} — RigDeck's device rule isn't installed "
                             "(re-run the installer)") from e
        except OSError as e:
            raise MouseError(f"can't open {node}: {e.strerror}") from e
        self.info: dict = {}

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        try:
            self._drain()
            self.handshake()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, *exc):
        self.close()

    def _drain(self):
        while select.select([self.fd], [], [], 0)[0]:
            try:
                if not os.read(self.fd, 64):
                    return
            except OSError:
                return

    def xfer(self, pkt: bytes) -> bytes | None:
        """Send until a reply echoes the request (5 bytes for flash reads, else 3). Returns the
        16-byte reply or None."""
        echo = 5 if pkt[0] == CMD_READ_FLASH else 3
        for _ in range(self.tries):
            os.write(self.fd, bytes([REPORT_ID]) + pkt)
            end = time.monotonic() + self.window
            while time.monotonic() < end:
                if not select.select([self.fd], [], [], 0.02)[0]:
                    continue
                try:
                    d = os.read(self.fd, 64)
                except BlockingIOError:
                    continue
                if len(d) >= 17 and d[0] == REPORT_ID and d[1:1 + echo] == pkt[:echo]:
                    return d[1:17]
        return None

    def request(self, pkt: bytes, what: str) -> bytes:
        r = self.xfer(pkt)
        if r is None:
            raise MouseError(f"the mouse didn't answer ({what}) — is it awake and in range?")
        return r

    def handshake(self):
        """Required before anything else. Also tells the model (cid/mid) and connection type."""
        nonce = bytes(random.randrange(256) for _ in range(4)) + bytes(4)
        r = self.request(packet(CMD_HANDSHAKE, nonce), "handshake")
        self.info = {"cid": r[9], "mid": r[10], "type": r[11]}
        self.xfer(packet(CMD_DRIVER, b"\x01"))  # "driver connected", as the vendor tool does

    def battery(self) -> dict | None:
        """{'level': %, 'charging': bool, 'mv': voltage} or None if the mouse doesn't report it."""
        r = self.xfer(packet(CMD_BATTERY))
        if r is None or r[5] > 100 or r[6] > 1:
            return None
        return {"level": r[5], "charging": r[6] == 1, "mv": (r[7] << 8) | r[8]}

    def read(self, addr: int, length: int) -> bytes:
        out = bytearray()
        while length > 0:
            n = min(10, length)
            r = self.request(packet(CMD_READ_FLASH, addr=addr, length=n), f"read {addr}")
            out += r[5:5 + n]
            addr += n
            length -= n
        return bytes(out)

    def write(self, addr: int, data: bytes):
        """Write up to 10 bytes per packet (flash; takes effect immediately)."""
        for i in range(0, len(data), 10):
            chunk = data[i:i + 10]
            self.request(packet(CMD_WRITE_FLASH, chunk, addr=addr + i), f"write {addr + i}")

    def write_pair(self, addr: int, value: int):
        self.write(addr, pair(value))

    def backup(self) -> bytes:
        return self.read(0, SETTINGS_SIZE)
