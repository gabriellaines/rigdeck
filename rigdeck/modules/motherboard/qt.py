"""`motherboard` in QML: board identity, temperatures and fan headers (polled from sysfs)."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal

from . import driver_available, read

POLL_MS = 2000


class MotherboardBackend(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._s = read()
        self._driver = driver_available()
        self._timer = QTimer(self, interval=POLL_MS, timeout=self._poll)
        self._timer.start()

    def _poll(self):
        self._s = read()       # a few small sysfs files; cheap enough for the UI thread
        self.changed.emit()

    state = Property("QVariantMap", lambda self: self._s, notify=changed)
    driverAvailable = Property(bool, lambda self: self._driver, constant=True)
