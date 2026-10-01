"""Read CPU sensors from Linux sysfs/procfs for the cooler's live-data report."""
from __future__ import annotations

import glob
import os

_TEMP_DRIVERS = ("k10temp", "zenpower", "coretemp")


def _find_cpu_temp_input() -> str | None:
    for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        try:
            name = open(os.path.join(hw, "name")).read().strip()
        except OSError:
            continue
        if name not in _TEMP_DRIVERS:
            continue
        # Prefer Tctl (AMD) / Package id 0 (Intel), else temp1.
        for lbl in sorted(glob.glob(os.path.join(hw, "temp*_label"))):
            label = open(lbl).read().strip()
            if label in ("Tctl", "Tdie", "Package id 0"):
                return lbl.replace("_label", "_input")
        if os.path.exists(os.path.join(hw, "temp1_input")):
            return os.path.join(hw, "temp1_input")
    return None


def cpu_name() -> str:
    with open("/proc/cpuinfo") as f:
        for line in f:
            if line.startswith("model name"):
                name = line.split(":", 1)[1].strip()
                # GCC sends e.g. "AMD RYZEN 7 5700X"
                for junk in (" 8-Core Processor", " 6-Core Processor", " 12-Core Processor",
                             " 16-Core Processor", " Processor"):
                    name = name.replace(junk, "")
                return name.upper()
    return "CPU"


def is_amd() -> bool:
    with open("/proc/cpuinfo") as f:
        return "AuthenticAMD" in f.read(4096)


def core_counts() -> tuple[int, int]:
    """(physical cores, threads)."""
    threads = os.cpu_count() or 0
    cores = set()
    with open("/proc/cpuinfo") as f:
        phys = core = None
        for line in f:
            if line.startswith("physical id"):
                phys = line.split(":")[1].strip()
            elif line.startswith("core id"):
                core = line.split(":")[1].strip()
                cores.add((phys, core))
    return (len(cores) or threads), threads


class CpuSensors:
    def __init__(self):
        self.temp_path = _find_cpu_temp_input()
        self._prev = self._stat()

    @staticmethod
    def _stat() -> tuple[int, int]:
        with open("/proc/stat") as f:
            vals = [int(v) for v in f.readline().split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        return sum(vals), idle

    def temperature(self) -> int:
        if not self.temp_path:
            return 0
        try:
            return round(int(open(self.temp_path).read()) / 1000)
        except OSError:
            return 0

    def load(self) -> int:
        total, idle = self._stat()
        dt, di = total - self._prev[0], idle - self._prev[1]
        self._prev = (total, idle)
        return round(100 * (dt - di) / dt) if dt > 0 else 0

    @staticmethod
    def freq_mhz() -> int:
        """Average current clock across all cores (what most monitors show)."""
        freqs = []
        for p in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
            try:
                freqs.append(int(open(p).read()))
            except OSError:
                pass
        return sum(freqs) // len(freqs) // 1000 if freqs else 0
