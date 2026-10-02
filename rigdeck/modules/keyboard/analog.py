"""Analog settings (actuation point, Rapid Trigger) of the PRO X TKL RAPID.

The keyboard keeps them as small files in its flash, reached through 0x8101 (profile management);
see docs/protocols/logitech-pro-x-tkl-rapid.md. Reading uses the calls G HUB uses (fn 8 opens a
sector, fn 12 returns its next 16 bytes). Writing sends files the way G HUB does (fn 2 length,
fn 3 chunks, fn 9 commit with CRC-32): that changes the *live* settings only — the stored profiles
are untouched, and fn 9 "activate" points a file back at the profile's stored copy.

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
# Every key id G HUB's actuation file lists (the 87 keys of this TKL + other layouts' keys).
FILE_IDS = list(range(0x00, 0x5D)) + list(range(0x64, 0x6B)) + [0x6E, 0x6F]
ACTUATION_RANGE = (1, 40)          # 0.1–4.0 mm
RAPID_RANGE = (1, 40)


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


# ---- writing (live settings) -------------------------------------------------------------

def pairs_file(values: dict[int, int]) -> bytes:
    return len(values).to_bytes(2, "big") + b"".join(bytes([k, v]) for k, v in values.items())


def write_file(k: hidpp.Device, file: int, data: bytes):
    k.feature(PROFILE_MGMT, 2, len(data).to_bytes(2, "big") + b"\0")
    for off in range(0, len(data), 16):
        chunk = data[off:off + 16]
        k.feature(PROFILE_MGMT, 3, chunk + bytes(16 - len(chunk)))
    k.feature(PROFILE_MGMT, 9, ANALOG.to_bytes(2, "big") + bytes([file, 2]) + len(data).to_bytes(3, "big")
              + zlib.crc32(data).to_bytes(4, "big"))


def _check(values: dict[int, int], lo_hi: tuple[int, int], what: str):
    lo, hi = lo_hi
    for kid, v in values.items():
        if kid not in KEYS:
            raise ValueError(f"unknown key id 0x{kid:02x}")
        if not lo <= v <= hi:
            raise ValueError(f"{what} for {KEYS[kid]} must be {mm(lo)}–{mm(hi)}")


def apply(k: hidpp.Device, default: int, actuation: dict[int, int], rapid: dict[int, int]):
    """Live settings: every key at `default` (0.1 mm) except `actuation` overrides; Rapid Trigger with
    per-key sensitivity on the keys in `rapid` (empty = off). Same order as G HUB: files 0, 1, 3."""
    _check({0: default}, ACTUATION_RANGE, "actuation")
    _check(actuation, ACTUATION_RANGE, "actuation")
    _check(rapid, RAPID_RANGE, "Rapid Trigger sensitivity")
    k.feature(ANALOG, 2, bytes([1 if rapid else 0]))       # Rapid Trigger master switch (G HUB sends it first)
    write_file(k, 0, pairs_file({kid: actuation.get(kid, default) for kid in FILE_IDS}))
    write_file(k, 1, pairs_file(dict(sorted(rapid.items()))))
    write_file(k, 3, pairs_file({}))


def restore(k: hidpp.Device, profile_index: int):
    """Drop live settings: point files 0 and 1 back at what the profile stores (empty if none)."""
    r = Reader(k)
    entries = sorted(i for i, e in r.directory(0).items() if e["feature"] == PROFILE_MGMT)
    p = parse_profile(r.file(0, entries[profile_index - 1], PROFILE_MGMT))
    k.feature(ANALOG, 2, bytes([1 if p["rapidTrigger"] else 0]))
    for file in (0, 1):
        ref = p["refs"][file]
        if ref is None or ref[0] != 0:
            write_file(k, file, pairs_file({kid: p["default"] for kid in FILE_IDS}) if file == 0 else pairs_file({}))
            continue
        e = r.directory(0)[ref[1]]
        k.feature(PROFILE_MGMT, 9, ANALOG.to_bytes(2, "big") + bytes([file, 0, ref[1]])
                  + e["length"].to_bytes(2, "big") + e["crc"].to_bytes(4, "big"))


def active_profile(k: hidpp.Device) -> int:
    """1–3: the onboard profile in use (0x8101 fn 6 `0f` → `03 00 <profile>`; switching wipes live settings)."""
    return k.feature(PROFILE_MGMT, 6, b"\x0f")[2]


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
