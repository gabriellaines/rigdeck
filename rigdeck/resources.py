"""Live resource usage (CPU, memory, disks, network, GPU) and CPU specifications, from /proc and
/sys — no root needed. `Sampler.sample()` returns rates since the previous call.
"""
from __future__ import annotations

import glob
import os
import time

from . import hwinfo
from .sensors import core_counts, cpu_name

CPU = "/sys/devices/system/cpu"


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


# ---- CPU specifications ---------------------------------------------------------------

ISA = [("sse4_2", "SSE4.2"), ("avx", "AVX"), ("avx2", "AVX2"), ("fma", "FMA3"), ("avx512f", "AVX-512"),
       ("avx_vnni", "AVX-VNNI"), ("sha_ni", "SHA"), ("aes", "AES-NI"), ("bmi2", "BMI2")]


def _size(s: str) -> int:
    """'32K' / '32768K' / '1M' -> bytes."""
    s = s.strip().upper()
    mult = {"K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}.get(s[-1:], 1)
    return int(s.rstrip("KMG") or 0) * mult


def caches() -> list[dict]:
    """[{level, type, size (bytes, per instance), instances}] from cpu*/cache."""
    seen: dict[tuple, set] = {}
    sizes: dict[tuple, int] = {}
    for idx in glob.glob(f"{CPU}/cpu[0-9]*/cache/index*"):
        key = (_read(f"{idx}/level"), _read(f"{idx}/type"))
        sizes[key] = _size(_read(f"{idx}/size"))
        seen.setdefault(key, set()).add(_read(f"{idx}/shared_cpu_list"))
    order = {"Data": 0, "Instruction": 1, "Unified": 2}
    return [{"level": int(k[0]), "type": k[1], "size": sizes[k], "instances": len(v)}
            for k, v in sorted(seen.items(), key=lambda kv: (kv[0][0], order.get(kv[0][1], 3)))]


def cpu_specs() -> dict:
    cores, threads = core_counts()
    flags = set()
    microcode = ""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("flags") and not flags:
                    flags = set(line.split(":", 1)[1].split())
                elif line.startswith("microcode") and not microcode:
                    microcode = line.split(":", 1)[1].strip()
    except OSError:
        pass
    cf = f"{CPU}/cpu0/cpufreq"
    virt = "AMD-V" if "svm" in flags else "VT-x" if "vmx" in flags else ""
    base = _int(f"{CPU}/cpu0/acpi_cppc/nominal_freq") or (_int(f"{cf}/base_frequency") or 0) // 1000 or None
    return {
        "name": cpu_name(), "cores": cores, "threads": threads,
        "smt": _read(f"{CPU}/smt/active") == "1",
        "baseMhz": base,
        "maxMhz": (_int(f"{cf}/cpuinfo_max_freq") or 0) // 1000 or None,
        "minMhz": (_int(f"{cf}/cpuinfo_min_freq") or 0) // 1000 or None,
        "caches": caches(),
        "virtualization": virt,
        "virtualizationEnabled": bool(virt) and os.path.exists("/dev/kvm"),
        "isa": [label for flag, label in ISA if flag in flags],
        "microcode": microcode,
        "driver": _read(f"{cf}/scaling_driver"), "governor": _read(f"{cf}/scaling_governor"),
        "epp": _read(f"{cf}/energy_performance_preference"),
        "pstate": _read(f"{CPU}/amd_pstate/status") or _read(f"{CPU}/intel_pstate/status"),
        "boost": _read(f"{cf}/boost") != "0" if os.path.exists(f"{cf}/boost") else None,
    }


# ---- live sampling --------------------------------------------------------------------

def _disks() -> list[str]:
    """Whole physical disks (no partitions, loop, zram, device-mapper)."""
    out = []
    for d in sorted(os.listdir("/sys/block")):
        if d.startswith(("loop", "zram", "ram", "dm-", "md", "sr")):
            continue
        if os.path.exists(f"/sys/block/{d}/device"):
            out.append(d)
    return out


def disk_info(name: str) -> dict:
    dev = f"/sys/block/{name}/device"
    model = _read(f"{dev}/model")
    return {"name": name, "model": model, "firmware": _read(f"{dev}/firmware_rev") or _read(f"{dev}/rev"),
            "size": (_int(f"/sys/block/{name}/size") or 0) * 512,
            "kind": "NVMe SSD" if name.startswith("nvme") else
                    ("Hard disk" if _read(f"/sys/block/{name}/queue/rotational") == "1" else "SSD")}


def _diskstats() -> dict[str, tuple[int, int, int]]:
    """name -> (bytes read, bytes written, ms busy)."""
    out = {}
    try:
        with open("/proc/diskstats") as f:
            for line in f:
                p = line.split()
                if len(p) >= 13:
                    out[p[2]] = (int(p[5]) * 512, int(p[9]) * 512, int(p[12]))
    except OSError:
        pass
    return out


def _netdevs() -> list[str]:
    return sorted(d for d in os.listdir("/sys/class/net") if os.path.exists(f"/sys/class/net/{d}/device"))


def _netstats(dev: str) -> tuple[int, int]:
    s = f"/sys/class/net/{dev}/statistics"
    return _int(f"{s}/rx_bytes") or 0, _int(f"{s}/tx_bytes") or 0


def system_activity() -> dict:
    """Processes, threads and seconds since boot, like Task Manager's CPU stats."""
    try:
        procs = sum(1 for d in os.listdir("/proc") if d.isdigit())
    except OSError:
        procs = 0
    loadavg = _read("/proc/loadavg").split()          # "0.18 0.32 0.46 1/2164 38375"
    threads = int(loadavg[3].split("/")[1]) if len(loadavg) > 3 and "/" in loadavg[3] else 0
    try:
        uptime = int(float(_read("/proc/uptime").split()[0]))
    except (ValueError, IndexError):
        uptime = 0
    return {"processes": procs, "threads": threads, "uptime": uptime}


class Sampler:
    """Call sample() periodically; each call returns usage since the previous one."""

    def __init__(self):
        self.load = hwinfo.CpuLoad()
        self.cards = hwinfo.gpu_cards()
        self.last_t = time.monotonic()
        self.last_disk = _diskstats()
        self.last_net = {d: _netstats(d) for d in _netdevs()}

    def sample(self) -> dict:
        now = time.monotonic()
        dt = max(now - self.last_t, 0.001)
        self.last_t = now

        loads = self.load.sample()
        freqs = hwinfo.cpu_freqs_mhz()
        cpu = {"total": loads.get("cpu", 0), "cores": [loads.get(f"cpu{i}", 0) for i in range(len(freqs))],
               "mhz": freqs, **system_activity()}

        disks = []
        stats = _diskstats()
        for name in _disks():
            r, w, busy = stats.get(name, (0, 0, 0))
            r0, w0, busy0 = self.last_disk.get(name, (r, w, busy))
            disks.append({"name": name, "read": max(0, r - r0) / dt, "write": max(0, w - w0) / dt,
                          "active": min(100.0, max(0, busy - busy0) / (dt * 10))})   # ms busy / ms elapsed
        self.last_disk = stats

        nets = []
        for dev in _netdevs():
            rx, tx = _netstats(dev)
            rx0, tx0 = self.last_net.get(dev, (rx, tx))
            self.last_net[dev] = (rx, tx)
            nets.append({"device": dev, "rx": max(0, rx - rx0) / dt, "tx": max(0, tx - tx0) / dt,
                         "wifi": os.path.isdir(f"/sys/class/net/{dev}/wireless"),
                         "up": _read(f"/sys/class/net/{dev}/operstate") == "up"})

        gpus = []
        for card in self.cards:                      # e.g. /sys/class/drm/card1
            dev = os.path.join(card, "device")
            used, total = _int(f"{dev}/mem_info_vram_used"), _int(f"{dev}/mem_info_vram_total")
            gpus.append({"card": card, "busy": _int(f"{dev}/gpu_busy_percent") or 0,
                         "vramUsed": used, "vramTotal": total})

        return {"cpu": cpu, "memory": hwinfo.memory(), "disks": disks, "nets": nets, "gpus": gpus}
