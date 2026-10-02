"""Memory modules from their SPD EEPROMs (JEDEC), which the kernel exposes world-readable through
the ee1004 (DDR4) and spd5118 (DDR5) drivers — no root needed.

DDR4 (512 bytes): byte 2 type (0x0C), 4 die density, 12 ranks/device width, 13 bus width,
18/125 minimum clock period (coarse 0.125 ns / fine ps), 320-321 maker (JEP106 bank, code),
329-348 part number; XMP 2.0 at 384 (signature 0C 4A), profile 1 voltage at 393, clock at 396/431.
DDR5 (1024 bytes): byte 2 = 0x12; maker at 512-513, part number at 521-550.
"""
from __future__ import annotations

import glob
import os

# (JEP106 bank, code) -> maker; bank = continuation count + 1
MAKERS = {(1, 0x2C): "Micron", (1, 0xCE): "Samsung", (1, 0xAD): "SK hynix", (2, 0x98): "Kingston",
          (3, 0x9E): "Corsair", (5, 0xCD): "G.Skill", (5, 0xCB): "ADATA", (5, 0xEF): "TeamGroup",
          (6, 0x9B): "Crucial"}
TYPES = {0x0C: "DDR4", 0x12: "DDR5", 0x0B: "DDR3"}
FORMS = {0x01: "RDIMM", 0x02: "UDIMM", 0x03: "SO-DIMM", 0x04: "LRDIMM"}


def _signed(b: int) -> int:
    return b - 256 if b > 127 else b


def mts_from_period(coarse: int, fine: int) -> int | None:
    ns = coarse * 0.125 + _signed(fine) / 1000
    if ns <= 0:
        return None
    rate = 2000 / ns
    # JEDEC speed bins: 1600, 1866, 2133, 2400, 2666, 2933, 3200…; snap to the nearest
    bins = [1333, 1600, 1866, 2133, 2400, 2666, 2933, 3200, 3466, 3600, 3733, 4000, 4266, 4400, 4800, 5200,
            5600, 6000, 6400, 6800, 7200, 7600, 8000]
    best = min(bins, key=lambda b: abs(b - rate))
    return best if abs(best - rate) / rate < 0.02 else round(rate)


def maker(bank_byte: int, code: int) -> str:
    bank = (bank_byte & 0x7F) + 1
    return MAKERS.get((bank, code), f"JEDEC {bank}/{code:#04x}")


def decode(b: bytes) -> dict:
    kind = TYPES.get(b[2], f"type {b[2]:#04x}") if len(b) > 2 else "unknown"
    out = {"type": kind, "form": FORMS.get(b[3] & 0x0F, "") if len(b) > 3 else ""}
    if b[2] == 0x0C and len(b) >= 512:                  # DDR4
        die_gbit = 0.25 * (1 << (b[4] & 0x0F))          # 0 = 256 Mbit … 5 = 8 Gbit
        width = 4 << (b[12] & 0x07)
        ranks = ((b[12] >> 3) & 0x07) + 1
        bus = 8 << (b[13] & 0x07)
        out["sizeGB"] = round(die_gbit / 8 * bus / width * ranks)
        out["ranks"] = ranks
        out["jedecMTs"] = mts_from_period(b[18], b[125])
        out["maker"] = maker(b[320], b[321])
        out["part"] = b[329:349].decode("ascii", errors="replace").strip()
        if b[384:386] == b"\x0c\x4a":                   # XMP 2.0
            out["xmpMTs"] = mts_from_period(b[396], b[431])
            out["xmpVolts"] = round(1 + (b[393] & 0x7F) / 100, 2)
    elif b[2] == 0x12 and len(b) >= 551:                # DDR5: identity only
        out["maker"] = maker(b[512], b[513])
        out["part"] = b[521:551].decode("ascii", errors="replace").strip()
    return out


def modules() -> list[dict]:
    """One entry per module whose SPD the kernel exposes, in SMBus address order."""
    out = []
    for drv in ("ee1004", "spd5118"):
        for dev in sorted(glob.glob(f"/sys/bus/i2c/drivers/{drv}/*-00[5-5][0-7]")):
            try:
                with open(os.path.join(dev, "eeprom"), "rb") as f:
                    data = f.read()
            except OSError:
                continue
            m = decode(data)
            m["address"] = "0x" + dev.rsplit("-", 1)[1][-2:]
            out.append(m)
    return out
