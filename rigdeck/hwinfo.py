"""Read-only hardware telemetry from sysfs/procfs: CPU, memory, storage, GPU.

Every function returns plain dicts/lists and never raises for missing data (None instead),
so pages work on any machine.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess

from .sensors import core_counts, cpu_name


def _read(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _int(path: str) -> int | None:
    v = _read(path)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _hwmon(dev_dir: str) -> str | None:
    found = glob.glob(os.path.join(dev_dir, "hwmon", "hwmon*")) or glob.glob(os.path.join(dev_dir, "hwmon[0-9]*"))
    return found[0] if found else None


def _labelled_temps(hw: str) -> dict[str, float]:
    out = {}
    for inp in sorted(glob.glob(os.path.join(hw, "temp*_input"))):
        label = _read(inp.replace("_input", "_label")) or os.path.basename(inp).split("_")[0]
        v = _int(inp)
        if v is not None:
            out[label] = v / 1000
    return out


# ---- CPU --------------------------------------------------------------------

class CpuLoad:
    """Per-core and total load from /proc/stat deltas."""

    def __init__(self):
        self.prev = self._stat()

    @staticmethod
    def _stat() -> dict[str, tuple[int, int]]:
        out = {}
        with open("/proc/stat") as f:
            for line in f:
                if not line.startswith("cpu"):
                    break
                parts = line.split()
                vals = [int(v) for v in parts[1:]]
                out[parts[0]] = (sum(vals), vals[3] + (vals[4] if len(vals) > 4 else 0))
        return out

    def sample(self) -> dict[str, int]:
        cur = self._stat()
        res = {}
        for k, (tot, idle) in cur.items():
            pt, pi = self.prev.get(k, (tot, idle))
            dt, di = tot - pt, idle - pi
            res[k] = round(100 * (dt - di) / dt) if dt > 0 else 0
        self.prev = cur
        return res


def cpu_static() -> dict:
    cores, threads = core_counts()
    base = "/sys/devices/system/cpu/cpu0/cpufreq/"
    return {"name": cpu_name(), "cores": cores, "threads": threads,
            "governor": _read(base + "scaling_governor"), "driver": _read(base + "scaling_driver"),
            "max_mhz": (_int(base + "cpuinfo_max_freq") or 0) // 1000 or None}


def cpu_freqs_mhz() -> list[int]:
    out = []
    for p in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"),
                    key=lambda s: int(s.split("/cpu")[2].split("/")[0])):
        v = _int(p)
        out.append(v // 1000 if v else 0)
    return out


# ---- memory -----------------------------------------------------------------

def memory() -> dict:
    info = {}
    with open("/proc/meminfo") as f:
        for line in f:
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0]) * 1024
    total, avail = info.get("MemTotal", 0), info.get("MemAvailable", 0)
    cached = info.get("Cached", 0) + info.get("Buffers", 0) + info.get("SReclaimable", 0)
    swap_t, swap_f = info.get("SwapTotal", 0), info.get("SwapFree", 0)
    zram = []
    for z in sorted(glob.glob("/sys/block/zram*")):
        mm = (_read(os.path.join(z, "mm_stat")) or "").split()
        if len(mm) >= 3:
            zram.append({"name": os.path.basename(z), "data": int(mm[0]), "compressed": int(mm[1]),
                         "ram_used": int(mm[2]),
                         "algorithm": (_read(os.path.join(z, "comp_algorithm")) or "").split("[")[-1].split("]")[0]})
    return {"total": total, "available": avail, "used": total - avail, "cached": cached,
            "swap_total": swap_t, "swap_used": swap_t - swap_f, "zram": zram}


# ---- storage ----------------------------------------------------------------

def storage() -> list[dict]:
    """Physical disks with model, size, transport, temperature and mounted filesystems."""
    try:
        out = subprocess.run(["lsblk", "-J", "-b", "-o",
                              "NAME,SIZE,TYPE,MODEL,TRAN,RM,MOUNTPOINTS,FSTYPE,LABEL,FSSIZE,FSUSED"],
                             capture_output=True, text=True, timeout=5).stdout
        tree = json.loads(out)["blockdevices"]
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        return []
    disks = []
    for d in tree:
        if d.get("type") != "disk" or d["name"].startswith(("zram", "loop")):
            continue
        hw = _hwmon(f"/sys/block/{d['name']}/device")
        temp = None
        if hw:
            t = _int(os.path.join(hw, "temp1_input"))
            temp = t / 1000 if t else None
        parts, seen = [], set()
        for p in d.get("children") or [d]:
            mounts = [m for m in (p.get("mountpoints") or []) if m]
            if not mounts or p["name"] in seen:
                continue
            seen.add(p["name"])
            mounts.sort(key=len)
            parts.append({"name": p["name"], "fstype": p.get("fstype"), "label": p.get("label"),
                          "mount": mounts[0], "size": int(p.get("fssize") or 0),
                          "used": int(p.get("fsused") or 0)})
        disks.append({"name": d["name"], "model": (d.get("model") or "").strip() or d["name"],
                      "size": int(d.get("size") or 0), "transport": (d.get("tran") or "").upper() or None,
                      "removable": bool(d.get("rm")), "temp": temp, "filesystems": parts})
    return disks


# ---- GPU --------------------------------------------------------------------

def _dpm_current(path: str) -> int | None:
    for line in (_read(path) or "").splitlines():
        if line.strip().endswith("*"):
            try:
                return int(line.split(":")[1].strip().rstrip("*").strip().lower().replace("mhz", ""))
            except (IndexError, ValueError):
                return None
    return None


def gpu_cards() -> list[str]:
    return sorted(c for c in glob.glob("/sys/class/drm/card[0-9]") if os.path.exists(c + "/device/vendor"))


def gpu_telemetry(card: str) -> dict:
    dev = os.path.join(card, "device")
    hw = _hwmon(dev)
    temps = _labelled_temps(hw) if hw else {}
    power = None
    if hw:
        p = _int(os.path.join(hw, "power1_average")) or _int(os.path.join(hw, "power1_input"))
        power = p / 1e6 if p else None
    cap = _int(os.path.join(hw, "power1_cap")) if hw else None
    return {"temp_edge": temps.get("edge"), "temp_junction": temps.get("junction"),
            "temp_mem": temps.get("mem"),
            "fan_rpm": _int(os.path.join(hw, "fan1_input")) if hw else None,
            "power_w": power, "power_cap_w": cap / 1e6 if cap else None,
            "busy": _int(os.path.join(dev, "gpu_busy_percent")),
            "vram_used": _int(os.path.join(dev, "mem_info_vram_used")),
            "vram_total": _int(os.path.join(dev, "mem_info_vram_total")),
            "sclk_mhz": _dpm_current(os.path.join(dev, "pp_dpm_sclk")),
            "mclk_mhz": _dpm_current(os.path.join(dev, "pp_dpm_mclk"))}


def session() -> str:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").replace(":", " / ")
    kind = os.environ.get("XDG_SESSION_TYPE", "").capitalize()
    nice = {"KDE": "KDE Plasma"}.get(desktop, desktop)
    return " · ".join(x for x in (kind, nice) if x) or "unknown"
