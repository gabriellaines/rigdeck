"""`mouse` in QML: connected mice, settings (written to the mouse's flash) and battery."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ...gui.bridge import run_async
from . import MAX_STAGES, backup, change, compx, connected, read_state

POLL_AWAKE_MS = 30000   # battery and settings
POLL_ASLEEP_MS = 4000   # notice quickly when it wakes up


class MouseBackend(QObject):
    miceChanged = Signal()
    stateChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._mice: list[dict] = []
        self._index = 0
        self._state: dict = {}
        self._status = "loading"   # loading | ok | asleep | none | error
        self._error = ""
        self._reading = False
        self._busy = False
        self._timer = QTimer(self, singleShot=True, timeout=self.refresh)
        self.refresh()

    def _dev(self) -> dict | None:
        return self._mice[self._index] if self._index < len(self._mice) else None

    # ---- reading -------------------------------------------------------------------------

    @Slot()
    def refresh(self):
        if self._reading or self._busy:
            return
        self._reading = True
        index = self._index

        def read():
            mice = connected()
            i = min(index, max(0, len(mice) - 1))
            return mice, i, (read_state(mice[i]) if mice else None)

        def got(r):
            self._reading = False
            mice, i, st = r
            if mice != self._mice or i != self._index:
                self._mice, self._index = mice, i
                self.miceChanged.emit()
            self._state = st or {}
            self._status = "none" if st is None else "asleep" if st["asleep"] else "ok"
            self._error = ""
            self.stateChanged.emit()
            self._timer.start(POLL_ASLEEP_MS if self._status != "ok" else POLL_AWAKE_MS)

        def failed(e):
            self._reading = False
            self._status, self._error = "error", str(e)
            self.stateChanged.emit()
            self._timer.start(POLL_ASLEEP_MS)
        run_async(read, got, failed)

    @Property("QVariantList", notify=miceChanged)
    def mice(self):
        from . import MODELS
        return [{"name": MODELS[d["model"]]["name"], "node": d["node"]} for d in self._mice]

    index = Property(int, lambda self: self._index, notify=miceChanged)
    state = Property("QVariantMap", lambda self: self._state, notify=stateChanged)
    status = Property(str, lambda self: self._status, notify=stateChanged)
    error = Property(str, lambda self: self._error, notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    maxStages = Property(int, lambda self: MAX_STAGES, constant=True)
    rates = Property("QVariantList", lambda self: sorted(compx.RATE_CODES), constant=True)

    @Property("QVariantMap", notify=stateChanged)
    def summary(self):
        s, st = self._state, self._status
        b = s.get("battery") or {}
        n = len(self._mice)
        status = {"ok": "Connected", "asleep": "Asleep", "none": "Not found", "loading": "…",
                  "error": "Error"}[st]
        if st == "ok" and b:
            status = f"{b['level']}% battery" + (" · charging" if b.get("charging") else "")
        return {"id": "mouse", "icon": "mouse", "title": s.get("name") or "Mouse",
                "detail": (s.get("connection", "").capitalize() + (f" · {n} mice" if n > 1 else "")) or "",
                "status": status, "connected": st == "ok",
                "tone": "live" if st == "ok" else "warning" if st in ("asleep", "loading") else "error",
                "battery": b.get("level") if st == "ok" else None}

    @Slot(int)
    def select(self, i):
        if 0 <= i < len(self._mice) and i != self._index:
            self._index = i
            self._state, self._status = {}, "loading"
            self.miceChanged.emit()
            self.stateChanged.emit()
            self.refresh()

    # ---- writing -------------------------------------------------------------------------

    def _write(self, changes: dict, done_text: str = ""):
        dev = self._dev()
        if self._busy or not dev:
            return
        self._busy = True
        self.stateChanged.emit()

        def work():
            if "stages" in changes:   # list of (index, dpi)
                for i, dpi in changes.pop("stages"):
                    change(dev, {"stage": (i, dpi)})
            if changes:
                change(dev, changes)

        def done(_):
            self._busy = False
            if done_text:
                self.toast.emit(done_text)
            self.refresh()

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not change the mouse: {e}")
            self.refresh()
        run_async(work, done, failed)

    @Slot(int)
    def setRate(self, hz):
        self._write({"rate": hz})

    @Slot(str, bool)
    def setSwitch(self, key, on):
        self._write({key: on})

    @Slot(int)
    def setCurrentStage(self, i):
        self._write({"currentStage": i})

    @Slot("QVariantList", int)
    def applyStages(self, dpis, count):
        """All stage DPIs (first `count` used) and the number of stages, in one go."""
        self._write({"stages": [(i, int(d)) for i, d in enumerate(dpis[:count])], "stageCount": int(count)},
                    "DPI stages saved on the mouse")

    @Slot(int, str)
    def setStageColor(self, i, color):
        self._write({"color": (i, color)})

    @Slot("QVariantMap")
    def setLed(self, led):
        self._write({"led": dict(led)})

    @Slot()
    def backupNow(self):
        dev = self._dev()
        if not dev:
            return

        def work():
            with compx.Mouse(dev["node"]) as m:
                return backup(m, dev["model"])
        run_async(work, lambda p: self.toast.emit(f"Saved to {p}"),
                  lambda e: self.toast.emit(f"Backup failed: {e}"))
