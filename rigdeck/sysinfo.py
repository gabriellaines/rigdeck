"""System overview: CPU, GPU, drivers, kernel. Everything optional; missing data -> None."""
from __future__ import annotations

import glob
import os
import platform
import re
import subprocess
from functools import lru_cache

from .sensors import cpu_name

PCI_VENDORS = {"0x1002": "AMD", "0x10de": "NVIDIA", "0x8086": "Intel"}


def _read(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def gpus() -> list[dict]:
    """One entry per DRM card: vendor, kernel driver, VBIOS, Vulkan name/driver."""
    vk = list(_vulkan())
    out = []
    for card in sorted(glob.glob("/sys/class/drm/card[0-9]")):
        dev = os.path.join(card, "device")
        vendor = _read(os.path.join(dev, "vendor"))
        driver = os.path.basename(os.path.realpath(os.path.join(dev, "driver"))) if os.path.exists(
            os.path.join(dev, "driver")) else None
        info = {"card": os.path.basename(card), "vendor": PCI_VENDORS.get(vendor, vendor),
                "kernel_driver": driver, "vbios": _read(os.path.join(dev, "vbios_version")),
                "pci": os.path.basename(os.path.realpath(dev))}
        info.update(vk.pop(0) if vk else {})
        out.append(info)
    return out


@lru_cache(maxsize=1)
def _vulkan() -> tuple[dict, ...]:
    text = _run("vulkaninfo", "--summary")
    devices, cur = [], None
    for line in text.splitlines():
        m = re.match(r"\s*(deviceName|driverName|driverInfo|apiVersion|deviceType)\s*=\s*(.+)", line)
        if not m:
            continue
        key, val = m.groups()
        if key == "apiVersion":
            cur = {"vulkan_api": val.strip()}
            devices.append(cur)
        elif cur is not None:
            cur[key] = val.strip()
    # drop software rasterisers (llvmpipe)
    return tuple({"name": d.get("deviceName"), "vulkan_driver": d.get("driverName"),
             "driver_version": d.get("driverInfo"), "vulkan_api": d.get("vulkan_api")}
            for d in devices if "CPU" not in d.get("deviceType", ""))


def mesa_version() -> str | None:
    for g in _vulkan():
        m = re.search(r"Mesa ([\d.]+\S*)", g.get("driver_version") or "")
        if m:
            return m.group(1)
    m = re.search(r"Mesa ([\d.]+\S*)", _run("glxinfo", "-B"))
    return m.group(1) if m else None


def overview() -> dict:
    os_name = None
    for line in (_read("/etc/os-release") or "").splitlines():
        if line.startswith("PRETTY_NAME="):
            os_name = line.split("=", 1)[1].strip('"')
    return {"cpu": cpu_name(), "kernel": platform.release(), "os": os_name,
            "mesa": mesa_version(), "gpus": gpus()}
