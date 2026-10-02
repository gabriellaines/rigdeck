"""`system` in QML: static system info plus live CPU / GPU / memory / storage telemetry."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal

from .. import hwinfo, sysinfo
from ..sensors import CpuSensors
from .activity import AdaptiveTimer
from .bridge import run_async

FAST_MS = 2000
STORAGE_MS = 30000


class SystemBackend(QObject):
    infoChanged = Signal()
    liveChanged = Signal()
    storageChanged = Signal()

    def __init__(self):
        super().__init__()
        self._info: dict = {"cpu": hwinfo.cpu_static(), "session": hwinfo.session(), "gpus": [],
                            "os": None, "kernel": None, "mesa": None}
        self._live: dict = {}
        self._storage: list = []
        self._sensors = CpuSensors()
        self._load = hwinfo.CpuLoad()
        self._cards = hwinfo.gpu_cards()
        run_async(sysinfo.overview, self._got_info)
        self._timer = AdaptiveTimer(self, self._poll, visible_ms=FAST_MS)            # paused when hidden
        self._poll()
        self._storage_timer = AdaptiveTimer(self, self._poll_storage, page="storage", page_ms=STORAGE_MS)
        self._poll_storage()

    def _got_info(self, o):
        gpus = o.get("gpus") or []
        for g in gpus:
            card = f"/sys/class/drm/{g['card']}"
            vram = hwinfo.gpu_telemetry(card).get("vram_total")
            g["vram_gb"] = round(vram / 2**30) if vram else None
        o = {k: v for k, v in o.items() if k != "cpu"}  # keep the detailed CPU record
        self._info.update(o)
        self._info["gpus"] = gpus
        self.infoChanged.emit()

    def _poll(self):
        loads = self._load.sample()
        freqs = hwinfo.cpu_freqs_mhz()
        gpu = hwinfo.gpu_telemetry(self._cards[0]) if self._cards else {}
        self._live = {
            "cpuTemp": self._sensors.temperature() or None,
            "cpuLoad": loads.get("cpu", 0),
            "coreLoads": [loads.get(f"cpu{i}", 0) for i in range(len(freqs))],
            "coreMhz": freqs,
            "cpuMhz": sum(freqs) // len(freqs) if freqs else None,
            "memory": hwinfo.memory(),
            "gpu": gpu,
        }
        self.liveChanged.emit()

    def _poll_storage(self):
        run_async(hwinfo.storage, self._got_storage)

    def _got_storage(self, disks):
        self._storage = disks
        self.storageChanged.emit()

    info = Property("QVariantMap", lambda self: self._info, notify=infoChanged)
    live = Property("QVariantMap", lambda self: self._live, notify=liveChanged)
    storage = Property("QVariantList", lambda self: self._storage, notify=storageChanged)
