"""Drive health (SMART) through UDisks2 — the desktop's disk service, so no root needed.

NVMe: wear (percent used), spare capacity, data read/written, power-on hours, power cycles,
unsafe shutdowns, media errors, critical warnings. SATA: SMART verdict, bad sectors, failing
attributes, power-on hours. Temperatures come in kelvin from UDisks.
"""
from __future__ import annotations

import json
import shutil
import subprocess

UD = "org.freedesktop.UDisks2"
ROOT = "/org/freedesktop/UDisks2"


def _call(path: str, iface: str, method: str, *args: str):
    r = subprocess.run(["busctl", "--system", "--json=short", "call", UD, path, iface, method, *args],
                       capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        return None
    data = json.loads(r.stdout)["data"]
    return data[0] if data else None


def _props(path: str, iface: str) -> dict:
    d = _call(path, "org.freedesktop.DBus.Properties", "GetAll", "s", iface)
    return {k: v["data"] for k, v in d.items()} if d else {}


def _c(kelvin) -> float | None:
    return round(kelvin - 273.15) if kelvin else None


def parse_nvme(ctrl: dict, attrs: dict) -> dict:
    a = {k: v["data"] if isinstance(v, dict) else v for k, v in (attrs or {}).items()}
    warnings = list(ctrl.get("SmartCriticalWarning") or [])
    out = {"kind": "nvme", "temperature": _c(ctrl.get("SmartTemperature")),
           "powerOnHours": ctrl.get("SmartPowerOnHours"), "selftest": ctrl.get("SmartSelftestStatus", ""),
           "wear": a.get("percent_used"), "spare": a.get("avail_spare"), "spareThreshold": a.get("spare_thresh"),
           "read": a.get("total_data_read"), "written": a.get("total_data_written"),
           "powerCycles": a.get("power_cycles"), "unsafeShutdowns": a.get("unsafe_shutdowns"),
           "mediaErrors": a.get("media_errors"), "warnings": warnings}
    out["ok"] = not warnings and not out["mediaErrors"] and (out["spare"] is None or out["spareThreshold"] is None
                                                              or out["spare"] > out["spareThreshold"])
    return out


def parse_ata(ata: dict) -> dict:
    out = {"kind": "ata", "temperature": _c(ata.get("SmartTemperature")),
           "powerOnHours": round(ata["SmartPowerOnSeconds"] / 3600) if ata.get("SmartPowerOnSeconds") else None,
           "selftest": ata.get("SmartSelftestStatus", ""), "badSectors": ata.get("SmartNumBadSectors"),
           "failingAttributes": ata.get("SmartNumAttributesFailing"),
           "failedInPast": ata.get("SmartNumAttributesFailedInThePast"), "smartEnabled": ata.get("SmartEnabled")}
    out["ok"] = not ata.get("SmartFailing") and not out["badSectors"] and not out["failingAttributes"]
    return out


def health(block: str) -> dict | None:
    """SMART health for a whole disk (e.g. 'nvme0n1'), or None if UDisks can't tell."""
    if not shutil.which("busctl"):
        return None
    try:
        drive = _call(f"{ROOT}/block_devices/{block}", "org.freedesktop.DBus.Properties", "Get", "ss",
                      "org.freedesktop.UDisks2.Block", "Drive")
        path = drive["data"] if isinstance(drive, dict) else None
        if not path or path == "/":
            return None
        info = _props(path, "org.freedesktop.UDisks2.Drive")
        ctrl = _props(path, "org.freedesktop.UDisks2.NVMe.Controller")
        if ctrl:
            out = parse_nvme(ctrl, _call(path, "org.freedesktop.UDisks2.NVMe.Controller", "SmartGetAttributes",
                                         "a{sv}", "0"))
        else:
            ata = _props(path, "org.freedesktop.UDisks2.Drive.Ata")
            if not ata.get("SmartSupported"):
                return None
            out = parse_ata(ata)
        out["serial"] = info.get("Serial", "")
        return out
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return None
