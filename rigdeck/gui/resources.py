"""`usage` in QML: a minute of history for CPU (total and per thread), memory, disks,
network adapters and GPUs, sampled every second — shared by the Resources and Processor pages."""
from __future__ import annotations

import os

from PySide6.QtCore import Property, QObject, Signal

from .. import disk_health, resources, spd
from .activity import AdaptiveTimer
from .bridge import run_async

HISTORY = 60      # samples kept (one per second)
INTERVAL_MS = 1000
HEALTH_MS = 5 * 60 * 1000   # SMART changes slowly


def _push(series: list, value):
    series.append(value)
    del series[:-HISTORY]


class ResourceMonitor(QObject):
    changed = Signal()

    def __init__(self, gpu_names: dict | None = None):
        super().__init__()
        self._sampler = resources.Sampler()
        self._specs = resources.cpu_specs()
        self._disk_info = {d: resources.disk_info(d) for d in resources._disks()}
        self._gpu_names = gpu_names or {}
        self._h: dict = {"cpu": [], "cores": [], "memory": [], "disks": {}, "nets": {}, "gpus": {}}
        self._now: dict = {}
        AdaptiveTimer(self, self._tick, visible_ms=INTERVAL_MS)
        try:
            self._modules = spd.modules()
        except OSError:
            self._modules = []
        self._health: dict = {}
        AdaptiveTimer(self, self._read_health, visible_ms=HEALTH_MS)
        self._read_health()

    healthChanged = Signal()

    def _read_health(self):
        disks = list(self._disk_info)
        run_async(lambda: {d: disk_health.health(d) for d in disks}, self._got_health)

    def _got_health(self, h):
        self._health = {k: v for k, v in h.items() if v}
        self.healthChanged.emit()

    def _tick(self):
        s = self._sampler.sample()   # a dozen small /proc and /sys reads: fine on the UI thread
        h = self._h
        _push(h["cpu"], s["cpu"]["total"])
        while len(h["cores"]) < len(s["cpu"]["cores"]):
            h["cores"].append([])
        for i, v in enumerate(s["cpu"]["cores"]):
            _push(h["cores"][i], v)
        m = s["memory"]
        _push(h["memory"], round(100 * m["used"] / m["total"], 1) if m.get("total") else 0)
        for d in s["disks"]:
            dh = h["disks"].setdefault(d["name"], {"active": [], "read": [], "write": []})
            for k in ("active", "read", "write"):
                _push(dh[k], d[k])
            if d["name"] not in self._disk_info:
                self._disk_info[d["name"]] = resources.disk_info(d["name"])
        for n in s["nets"]:
            nh = h["nets"].setdefault(n["device"], {"rx": [], "tx": []})
            _push(nh["rx"], n["rx"])
            _push(nh["tx"], n["tx"])
        for g in s["gpus"]:
            gh = h["gpus"].setdefault(g["card"], {"busy": [], "vram": []})
            _push(gh["busy"], g["busy"])
            _push(gh["vram"], round(100 * g["vramUsed"] / g["vramTotal"], 1) if g["vramTotal"] else 0)
        for d in s["disks"]:
            d.update(self._disk_info.get(d["name"], {}))
        for g in s["gpus"]:
            g["name"] = self._gpu_names.get(os.path.basename(g["card"]), "Graphics card")
        self._now = s
        self.changed.emit()

    history = Property("QVariantMap", lambda self: self._h, notify=changed)
    now = Property("QVariantMap", lambda self: self._now, notify=changed)
    specs = Property("QVariantMap", lambda self: self._specs, constant=True)
    historyLength = Property(int, lambda self: HISTORY, constant=True)
    modules = Property("QVariantList", lambda self: self._modules, constant=True)
    health = Property("QVariantMap", lambda self: self._health, notify=healthChanged)
    disks = Property("QVariantMap", lambda self: self._disk_info, notify=changed)
