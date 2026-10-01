"""`motherboard` in QML: board identity, temperatures, fan headers (polled from sysfs) and lighting."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ...gui.bridge import run_async
from . import driver_available, lighting, read, set_lighting

POLL_MS = 2000


class MotherboardBackend(QObject):
    changed = Signal()
    lightingChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._s = read()
        self._driver = driver_available()
        self._light: dict = {}
        self._light_error = ""
        self._busy = False
        self._timer = QTimer(self, interval=POLL_MS, timeout=self._poll)
        self._timer.start()
        self.refreshLighting()

    def _poll(self):
        self._s = read()       # a few small sysfs files; cheap enough for the UI thread
        self.changed.emit()

    state = Property("QVariantMap", lambda self: self._s, notify=changed)
    driverAvailable = Property(bool, lambda self: self._driver, constant=True)

    # ---- lighting ------------------------------------------------------------------------

    @Slot()
    def refreshLighting(self):
        def got(info):
            self._light, self._light_error = info or {}, ""
            self.lightingChanged.emit()

        def failed(e):
            self._light, self._light_error = {}, str(e)
            self.lightingChanged.emit()
        run_async(lighting, got, failed)

    light = Property("QVariantMap", lambda self: self._light, notify=lightingChanged)
    lightError = Property(str, lambda self: self._light_error, notify=lightingChanged)
    busy = Property(bool, lambda self: self._busy, notify=lightingChanged)

    @Slot(str, str, str)
    def setLighting(self, zone, mode, color):
        if self._busy:
            return
        self._busy = True
        self.lightingChanged.emit()

        def done(_):
            self._busy = False
            self.refreshLighting()

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not change the lighting: {e}")
            self.lightingChanged.emit()
        run_async(lambda: set_lighting(zone, mode, color), done, failed)
