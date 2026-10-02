"""`keyboard` in QML: identity, lighting brightness, analog settings (read-only)."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...gui.activity import AdaptiveTimer
from ...gui.bridge import run_async
from . import BRIGHTNESS_PRESETS, analog_state, connected, read_state, set_brightness

POLL_MS = 10000   # picks up brightness changed with the Fn key


class KeyboardBackend(QObject):
    stateChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._state: dict = {}
        self._dev: dict | None = None
        self._status = "loading"   # loading | ok | none | error
        self._error = ""
        self._busy = False
        self._reading = False
        self._analog: list = []
        self._analog_status = "idle"   # idle | loading | ok | error
        self._timer = AdaptiveTimer(self, self.refresh, page="keyboard", page_ms=POLL_MS, visible_ms=60000)
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading or self._busy:
            return
        self._reading = True

        def read():
            kbs = connected()
            return (kbs[0], read_state(kbs[0])) if kbs else (None, None)

        def got(r):
            self._reading = False
            self._dev, st = r
            self._state = st or {}
            if not st:
                self._analog, self._analog_status = [], "idle"     # read again when it's back
            self._status = "ok" if st else "none"
            self._error = ""
            self.stateChanged.emit()
            if st and self._analog_status == "idle":
                self.refreshAnalog()

        def failed(e):
            self._reading = False
            self._status, self._error = "error", str(e)
            self.stateChanged.emit()
        run_async(read, got, failed)

    # ---- analog settings: ~150 small reads, so once per connection and on demand, not polled

    analogChanged = Signal()

    @Slot()
    def refreshAnalog(self):
        if self._analog_status == "loading" or not self._dev:
            return
        self._analog_status = "loading"
        self.analogChanged.emit()
        dev = self._dev

        def got(profiles):
            self._analog, self._analog_status = profiles, "ok"
            self.analogChanged.emit()

        def failed(e):
            self._analog_status = "error"
            self.toast.emit(f"Could not read the analog settings: {e}")
            self.analogChanged.emit()
        run_async(lambda: analog_state(dev), got, failed)

    analog = Property("QVariantList", lambda self: self._analog, notify=analogChanged)
    analogStatus = Property(str, lambda self: self._analog_status, notify=analogChanged)

    state = Property("QVariantMap", lambda self: self._state, notify=stateChanged)
    status = Property(str, lambda self: self._status, notify=stateChanged)
    error = Property(str, lambda self: self._error, notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    presets = Property("QVariantList", lambda self: BRIGHTNESS_PRESETS, constant=True)

    @Property("QVariantMap", notify=stateChanged)
    def summary(self):
        s, st = self._state, self._status
        return {"id": "keyboard", "icon": "keyboard", "title": s.get("name") or "Keyboard",
                "detail": f"USB 046d:{s['pid']}" if s.get("pid") else "",
                "status": {"ok": "Connected", "none": "Not found", "loading": "…", "error": "Error"}[st],
                "connected": st == "ok", "tone": "live" if st == "ok" else "warning", "battery": None}

    @Slot(int)
    def setBrightness(self, value):
        if self._busy or not self._dev:
            return
        self._busy = True
        self.stateChanged.emit()
        dev = self._dev

        def done(_):
            self._busy = False
            self._state = {**self._state, "brightness": value}
            self.stateChanged.emit()

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not change the keyboard: {e}")
            self.stateChanged.emit()
            self.refresh()
        run_async(lambda: set_brightness(dev, value), done, failed)
