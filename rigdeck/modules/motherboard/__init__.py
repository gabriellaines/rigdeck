"""Motherboard: model, BIOS, board temperatures and fan headers, from the Super I/O chip's
hwmon driver (nct6775 for Nuvoton chips, it87 for ITE). Read-only for now.

Fan control is deliberately not offered yet: it can only be verified with fans connected to the
headers, and a wrong write here can leave a CPU fan stopped.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess

from ..base import Module

SUPERIO = ("nct6", "it87", "it86", "it88", "w83")   # hwmon names of Super I/O drivers
DMI = "/sys/class/dmi/id"
# Friendly names for well-known Nuvoton temperature labels; anything else keeps its label.
TEMP_NAMES = {"SYSTIN": "Motherboard", "CPUTIN": "CPU socket", "TSI0_TEMP": "CPU (reported to the board)",
              "PCH_CHIP_TEMP": "Chipset", "PCH_CPU_TEMP": "CPU (chipset)", "PCH_MCH_TEMP": "Memory controller"}
# Inputs that read garbage unless a sensor is wired to them, and calibration values.
SKIP_TEMPS = ("AUXTIN", "PECI Agent", "PCH_CHIP_CPU_MAX_TEMP", "SMBUSMASTER")
FAN_MODES = {0: "Full speed", 1: "Manual", 2: "Thermal cruise", 3: "Speed cruise", 4: "BIOS curve",
             5: "BIOS curve", 6: "BIOS curve", 7: "BIOS curve"}


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def _int(path: str) -> int | None:
    try:
        return int(_read(path))
    except ValueError:
        return None


def sensor_dir() -> str | None:
    for h in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        if _read(os.path.join(h, "name")).startswith(SUPERIO):
            return h
    return None


def board() -> dict:
    return {k: _read(os.path.join(DMI, f)) for k, f in
            (("vendor", "board_vendor"), ("name", "board_name"), ("bios", "bios_version"),
             ("biosDate", "bios_date"), ("biosVendor", "bios_vendor"))}


def driver_available() -> bool:
    """The Nuvoton driver exists for this kernel (so loading it is a one-line fix)."""
    return subprocess.run(["modinfo", "-n", "nct6775"], capture_output=True).returncode == 0 \
        if shutil.which("modinfo") else False


def read() -> dict:
    h = sensor_dir()
    out = {"board": board(), "chip": _read(os.path.join(h, "name")) if h else "", "temps": [], "fans": []}
    if not h:
        return out
    for t in sorted(glob.glob(os.path.join(h, "temp*_input")), key=lambda p: int(p.split("temp")[-1].split("_")[0])):
        base = t[:-len("_input")]
        label = _read(base + "_label") or os.path.basename(base)
        v = _int(t)
        if v is None or label.startswith(SKIP_TEMPS) or not 0 < v / 1000 < 125:
            continue
        out["temps"].append({"label": TEMP_NAMES.get(label, label), "raw": label, "c": round(v / 1000, 1)})
    for f in sorted(glob.glob(os.path.join(h, "fan*_input")), key=lambda p: int(p.split("fan")[-1].split("_")[0])):
        n = int(os.path.basename(f)[3:].split("_")[0])
        pwm, enable = _int(os.path.join(h, f"pwm{n}")), _int(os.path.join(h, f"pwm{n}_enable"))
        rpm = _int(f) or 0
        out["fans"].append({"n": n, "rpm": rpm, "connected": rpm > 0,
                            "duty": round(100 * pwm / 255) if pwm is not None else None,
                            "mode": FAN_MODES.get(enable, "—") if enable is not None else "—"})
    return out


# ---- CLI ------------------------------------------------------------------------------

def cli_status(a):
    s = read()
    b = s["board"]
    print(f"{'Board':<14}{b['vendor']} {b['name']}")
    print(f"{'BIOS':<14}{b['bios']} ({b['biosDate']})")
    if not s["chip"]:
        print("Sensors       not available — the board's sensor driver isn't loaded"
              + (" (try: sudo modprobe nct6775)" if driver_available() else ""))
        return
    print(f"{'Sensor chip':<14}{s['chip']}")
    for t in s["temps"]:
        print(f"  {t['label']:<30}{t['c']:5.1f} °C")
    for f in s["fans"]:
        state = f"{f['rpm']} rpm" if f["connected"] else "no fan"
        print(f"  Fan header {f['n']:<19}{state:<10} {f['mode']}" + (f", {f['duty']}% power" if f["duty"] is not None else ""))


class MotherboardModule(Module):
    id = "motherboard"
    title = "Motherboard"
    icon = "circuit-board"
    kind = "system"
    order = 35

    def detect(self) -> bool:
        return os.path.exists(os.path.join(DMI, "board_name"))

    def add_cli(self, sub):
        sub.add_parser("motherboard", help="board, BIOS, board temperatures and fan headers")\
            .set_defaults(func=cli_status)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "MotherboardPage.qml")

    def qt_backend(self, app):
        from .qt import MotherboardBackend
        return MotherboardBackend()
