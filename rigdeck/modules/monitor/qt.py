"""`monitor` in QML: connected monitors, their controls, input changes that revert unless kept."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ...gui.activity import AdaptiveTimer
from ...gui.bridge import run_async
from . import ddc, monitors, set_value
from ... import vibrance

POLL_MS = 30000          # values can also change with the monitor's own buttons
INPUT_CONFIRM_S = 10


class MonitorBackend(QObject):
    monitorsChanged = Signal()
    confirmChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._mons: list[dict] = []
        self._status = "loading"   # loading | ok | none | not-installed | error
        self._error = ""
        self._reading = False
        self._queue: list[tuple] = []   # (bus, code, value, label) waiting to be written
        self._writing = False
        self._revert: tuple | None = None   # (bus, old input, monitor name) while asking to keep
        self._left = 0
        self._countdown = QTimer(self, interval=1000, timeout=self._tick)
        self._timer = AdaptiveTimer(self, self.refresh, page="monitor", page_ms=POLL_MS, visible_ms=300000)
        self._vib: list = []
        self._vib_ok = vibrance.available()
        self._vib_busy = False
        if self._vib_ok:
            AdaptiveTimer(self, self.refreshVibrance, page="monitor", page_ms=POLL_MS, start_now=True)
        self.refresh()

    # ---- reading -------------------------------------------------------------------------

    @Slot()
    def refresh(self):
        if self._reading or self._writing or self._queue:
            return
        self._reading = True

        def got(mons):
            self._reading = False
            self._mons = mons
            self._status, self._error = ("ok" if mons else "none"), ""
            self.monitorsChanged.emit()

        def failed(e):
            self._reading = False
            self._status = "not-installed" if isinstance(e, ddc.NotInstalled) else "error"
            self._error = str(e)
            self.monitorsChanged.emit()
        run_async(monitors, got, failed)

    monitors = Property("QVariantList", lambda self: self._mons, notify=monitorsChanged)
    status = Property(str, lambda self: self._status, notify=monitorsChanged)
    error = Property(str, lambda self: self._error, notify=monitorsChanged)
    busy = Property(bool, lambda self: self._writing, notify=monitorsChanged)

    @Property("QVariantMap", notify=monitorsChanged)
    def summary(self):
        n = len(self._mons)
        st = self._status
        return {"id": "monitor", "icon": "monitor-cog",
                "title": self._mons[0]["name"] if n == 1 else f"{n} monitors" if n else "Monitors",
                "detail": " · ".join(m["name"] for m in self._mons) if n > 1 else
                          (self._mons[0]["connector"] if n else "DDC/CI"),
                "status": {"ok": "Connected", "none": "None found", "loading": "…",
                           "not-installed": "Needs ddcutil", "error": "Error"}[st],
                "connected": st == "ok", "tone": "live" if st == "ok" else "warning", "battery": None}

    # ---- colour vibrance (KWin ICC profiles) -------------------------------------------------

    vibranceChanged = Signal()

    @Slot()
    def refreshVibrance(self):
        def got(outs):
            self._vib = outs
            self.vibranceChanged.emit()
        run_async(vibrance.outputs, got, lambda e: None)

    vibranceAvailable = Property(bool, lambda self: self._vib_ok, constant=True)
    vibranceOutputs = Property("QVariantList", lambda self: self._vib, notify=vibranceChanged)
    vibranceBusy = Property(bool, lambda self: self._vib_busy, notify=vibranceChanged)

    @Slot(str, int)
    def setVibrance(self, output, level):
        """output '' = every monitor."""
        if self._vib_busy:
            return
        self._vib_busy = True
        self.vibranceChanged.emit()
        names = [o["name"] for o in self._vib if not o["hdr"] and output in ("", o["name"])]

        def work():
            for n in names:
                vibrance.apply(n, level)

        def done(_):
            self._vib_busy = False
            self.refreshVibrance()

        def failed(e):
            self._vib_busy = False
            self.toast.emit(f"Vibrance: {e}")
            self.refreshVibrance()
        run_async(work, done, failed)

    # ---- writing (one ddcutil call at a time, in order) -------------------------------------

    def _local(self, bus: int, code: int, value: int):
        """Show the new value right away; the next read confirms it."""
        for m in self._mons:
            if m["bus"] == bus:
                for c in m["controls"]:
                    if c["code"] == code:
                        c["value"] = value
        self.monitorsChanged.emit()

    def _enqueue(self, bus, code, value, label=""):
        self._queue = [q for q in self._queue if (q[0], q[1]) != (bus, code)] + [(bus, code, int(value), label)]
        self._local(bus, code, int(value))
        self._flush()

    def _flush(self):
        if self._writing or not self._queue:
            return
        bus, code, value, label = self._queue.pop(0)
        self._writing = True

        def done(_):
            self._writing = False
            if self._queue:
                self._flush()
            else:
                self.monitorsChanged.emit()

        def failed(e):
            self._writing = False
            self.toast.emit(f"{label or 'Monitor'}: {e}")
            self._queue.clear()
            self.refresh()
        run_async(lambda: set_value(bus, code, value), done, failed)

    @Slot(int, int, int)
    def set(self, i, code, value):
        if 0 <= i < len(self._mons):
            m = self._mons[i]
            self._enqueue(m["bus"], code, value, m["name"])

    @Slot(int)
    def setAllBrightness(self, percent):
        """Same brightness on every monitor (as a share of each one's own maximum)."""
        for m in self._mons:
            c = next((c for c in m["controls"] if c["code"] == ddc.BRIGHTNESS), None)
            if c:
                self._enqueue(m["bus"], c["code"], round(percent * c["max"] / 100), m["name"])

    # ---- input changes: revert unless confirmed ----------------------------------------------

    @Slot(int, int)
    def setInput(self, i, value):
        if self._revert or not 0 <= i < len(self._mons):
            return
        m = self._mons[i]
        c = next((c for c in m["controls"] if c["code"] == ddc.INPUT), None)
        if c is None or c["value"] == value:
            return
        self._revert = (m["bus"], c["value"], m["name"])
        self._left = INPUT_CONFIRM_S
        self._enqueue(m["bus"], ddc.INPUT, value, m["name"])
        self._countdown.start()
        self.confirmChanged.emit()

    confirmSeconds = Property(int, lambda self: self._left, notify=confirmChanged)
    confirmName = Property(str, lambda self: self._revert[2] if self._revert else "", notify=confirmChanged)

    def _tick(self):
        self._left -= 1
        if self._left <= 0:
            self.keepInput(False)
        else:
            self.confirmChanged.emit()

    @Slot(bool)
    def keepInput(self, keep):
        self._countdown.stop()
        if self._revert and not keep:
            bus, old, name = self._revert
            self._enqueue(bus, ddc.INPUT, old, name)
            self.toast.emit(f"{name}: input switched back")
        self._revert, self._left = None, 0
        self.confirmChanged.emit()
