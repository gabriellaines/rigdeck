"""Analog settings (actuation point, Rapid Trigger) of the PRO X TKL RAPID — read-only.

The keyboard keeps them as small files in its flash, reached through 0x8101 (profile management);
see docs/protocols/logitech-pro-x-tkl-rapid.md. Only the calls G HUB itself makes to read are used
here: fn 8 opens a sector for reading, fn 12 returns its next 16 bytes. Nothing is written.

Each onboard profile (Fn+F2/F3/F4) ends with an analog table: the default actuation point, whether
Rapid Trigger is on, and pointers (bank, directory entry) to its 0x1b08 files:
file 0 = per-key actuation points, file 1 = per-key Rapid Trigger sensitivity. Values in 0.1 mm.
"""
from __future__ import annotations

import zlib

from . import hidpp
from .keymap import KEYS

PROFILE_MGMT, ANALOG = 0x8101, 0x1B08
DIR_LEN = 0x400
PROFILE_LEN = 0x6D
ANALOG_TABLE = 91                     # offset of the analog table inside a profile
PROFILE_KEYS = ["Fn + F2", "Fn + F3", "Fn + F4"]
TRAVEL_MM = 4.0


class FormatError(hidpp.HidppError):
    pass


def read_sector(k: hidpp.Device, bank: int, sector: int, length: int) -> bytes:
    k.feature(PROFILE_MGMT, 8, bytes([bank, sector]) + length.to_bytes(2, "big"))
    out = b""
    for off in range(0, length, 16):
        out += k.feature(PROFILE_MGMT, 12, off.to_bytes(2, "big"))
    return out[:length]


def parse_directory(d: bytes) -> dict[int, dict]:
    """{entry id: {feature, length, crc, sector}} from a bank's sector 0."""
    out, pos = {}, 5
    for _ in range(d[4]):
        e = d[pos:pos + 10]
        if len(e) < 10 or e[0] == 0xFF:
            break
        out[e[0]] = {"feature": int.from_bytes(e[1:3], "big"), "length": ((e[3] & 0x3F) << 8) | e[4],
                     "crc": int.from_bytes(e[5:9], "big"), "sector": e[9]}
        pos += 10
    return out


def parse_pairs(data: bytes) -> dict[int, int]:
    """[count hi, count lo] + count × [key id, value] → {key id: value}."""
    n = int.from_bytes(data[:2], "big")
    if 2 + 2 * n > len(data):
        raise FormatError("analog file shorter than its key count")
    return {data[2 + 2 * i]: data[3 + 2 * i] for i in range(n)}


def parse_profile(p: bytes) -> dict:
    t = p[ANALOG_TABLE:ANALOG_TABLE + 10]
    refs = [None if t[2 + 2 * i] == 0xFF else (t[2 + 2 * i], t[3 + 2 * i]) for i in range(4)]
    name = ""
    if p[6:8] != b"\xff\xff":
        name = p[6:38].decode("utf-16-be", errors="replace").split("\0")[0].strip()
    return {"default": t[0], "rapidTrigger": bool(t[1]), "refs": refs, "name": name}


class Reader:
    """Reads profiles and their analog files, checking each file against its directory CRC."""

    def __init__(self, k: hidpp.Device):
        self.k, self._dirs = k, {}

    def directory(self, bank: int) -> dict[int, dict]:
        if bank not in self._dirs:
            self._dirs[bank] = parse_directory(read_sector(self.k, bank, 0, DIR_LEN))
        return self._dirs[bank]

    def file(self, bank: int, entry: int, feature: int) -> bytes:
        e = self.directory(bank).get(entry)
        if e is None or e["feature"] != feature:
            raise FormatError(f"profile points at a missing file (bank {bank}, entry {entry})")
        data = read_sector(self.k, bank, e["sector"], e["length"])
        if zlib.crc32(data) != e["crc"]:
            raise FormatError(f"checksum mismatch reading bank {bank} entry {entry}")
        return data

    def profiles(self) -> list[dict]:
        out = []
        entries = sorted(i for i, e in self.directory(0).items() if e["feature"] == PROFILE_MGMT)
        for n, entry in enumerate(entries[:len(PROFILE_KEYS)]):
            p = parse_profile(self.file(0, entry, PROFILE_MGMT))
            actuation = {kid: p["default"] for kid in KEYS}
            if p["refs"][0]:
                actuation.update({kid: v for kid, v in parse_pairs(self.file(*p["refs"][0], ANALOG)).items()
                                  if kid in KEYS})
            rapid = {}
            if p["rapidTrigger"] and p["refs"][1]:
                rapid = {kid: v for kid, v in parse_pairs(self.file(*p["refs"][1], ANALOG)).items() if kid in KEYS}
            out.append({"index": n + 1, "keys": PROFILE_KEYS[n], "name": p["name"],
                        "default": p["default"], "actuation": actuation, "rapidTrigger": rapid})
        return out


def read_profiles(node: str) -> list[dict]:
    with hidpp.Device(node) as k:
        return Reader(k).profiles()


def mm(tenths: int) -> str:
    return f"{tenths / 10:.1f} mm"


def summary(values: dict[int, int]) -> list[tuple[str, list[str]]]:
    """Group keys by value, most common first: [("2.0 mm", [key names…]), …]."""
    groups: dict[int, list[str]] = {}
    for kid in sorted(values):
        groups.setdefault(values[kid], []).append(KEYS[kid])
    return [(mm(v), names) for v, names in sorted(groups.items(), key=lambda g: -len(g[1]))]
