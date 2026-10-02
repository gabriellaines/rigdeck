"""Monitor controls over DDC/CI, through ddcutil (https://www.ddcutil.com).

ddcutil's udev rule gives the logged-in user access to the graphics card's I2C buses (the
monitor cables), so no extra permissions are needed. Monitors are identified by model + serial,
because bus numbers can change between boots.

Value formats in `getvcp --terse` output:
    VCP 10 C 60 100                 continuous: current, maximum
    VCP 60 SNC x0f                  simple non-continuous: one byte
    VCP 62 CNC x00 x64 x00 x32      complex non-continuous: max hi, max lo, current hi, current lo
    VCP 62 ERR                      not supported / no answer
"""
from __future__ import annotations

import re
import shutil
import subprocess

from ..base import RigdeckError

EXE = "ddcutil"

BRIGHTNESS, CONTRAST, PRESET, INPUT, VOLUME, MUTE = 0x10, 0x12, 0x14, 0x60, 0x62, 0x8D
CONTINUOUS = {BRIGHTNESS, CONTRAST, VOLUME}


class DdcError(RigdeckError):
    pass


class NotInstalled(DdcError):
    pass


def installed() -> bool:
    return shutil.which(EXE) is not None


def _run(*args: str, timeout: float = 20, partial: bool = False) -> str:
    """ddcutil's output. With partial=True, a failure still returns whatever values it read
    (ddcutil exits non-zero when any one requested feature is unsupported)."""
    if not installed():
        raise NotInstalled("ddcutil is not installed")
    try:
        r = subprocess.run([EXE, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise DdcError("the monitor didn't answer in time") from e
    if r.returncode != 0 and not (partial and "VCP " in r.stdout):
        msg = [ln for ln in (r.stderr + r.stdout).strip().splitlines() if ln.strip()]
        raise DdcError(msg[-1].strip() if msg else f"ddcutil failed ({r.returncode})")
    return r.stdout


def parse_detect(out: str) -> list[dict]:
    """Displays from `ddcutil detect --terse` (skips 'Invalid display' entries)."""
    displays, cur = [], None
    for line in out.splitlines():
        if line.startswith("Display "):
            cur = {}
            displays.append(cur)
        elif line.startswith("Invalid display"):
            cur = None
        elif cur is not None and ":" in line:
            key, _, val = line.strip().partition(":")
            val = val.strip()
            if key == "I2C bus":
                cur["bus"] = int(val.rsplit("-", 1)[1])
            elif key == "DRM connector":
                cur["connector"] = val.split("-", 1)[1] if "-" in val else val    # card1-DP-2 -> DP-2
            elif key == "Monitor":
                mfg, model, serial = (val.split(":") + ["", "", ""])[:3]
                cur.update(mfg=mfg, model=model, serial=serial)
    return [d for d in displays if "bus" in d]


def parse_capabilities(out: str) -> dict[int, dict]:
    """{feature code: {'name': str, 'values': {code: label}}} from `ddcutil capabilities`."""
    feats: dict[int, dict] = {}
    cur = None
    for line in out.splitlines():
        m = re.match(r"\s*Feature: ([0-9A-Fa-f]{2}) \((.*)\)", line)
        if m:
            cur = feats[int(m.group(1), 16)] = {"name": m.group(2), "values": {}}
            continue
        m = re.match(r"\s+([0-9A-Fa-f]{2}): (.+)", line)
        if m and cur is not None:
            cur["values"][int(m.group(1), 16)] = m.group(2).strip()
    return feats


def parse_getvcp(out: str) -> dict[int, dict]:
    """{code: {'cur': int, 'max': int | None}} — max is None for one-of-a-list values."""
    vals: dict[int, dict] = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) < 3 or p[0] != "VCP":
            continue
        code, kind = int(p[1], 16), p[2]
        try:
            if kind == "C":
                vals[code] = {"cur": int(p[3]), "max": int(p[4])}
            elif kind == "SNC":
                vals[code] = {"cur": int(p[3].lstrip("x"), 16), "max": None}
            elif kind == "CNC":
                mh, ml, sh, sl = (int(x.lstrip("x"), 16) for x in p[3:7])
                cur, mx = (sh << 8) | sl, (mh << 8) | ml
                vals[code] = {"cur": cur, "max": mx if code in CONTINUOUS else None}
        except (IndexError, ValueError):
            continue
    return vals


def detect() -> list[dict]:
    return parse_detect(_run("detect", "--terse"))


def capabilities(bus: int) -> dict[int, dict]:
    return parse_capabilities(_run("--bus", str(bus), "capabilities"))


def get(bus: int, codes) -> dict[int, dict]:
    return parse_getvcp(_run("--bus", str(bus), "getvcp", *(f"{c:02x}" for c in codes), "--terse", partial=True))


def set(bus: int, code: int, value: int):  # noqa: A001 — mirrors ddcutil's setvcp
    _run("--bus", str(bus), "setvcp", f"{code:02x}", str(int(value)))
