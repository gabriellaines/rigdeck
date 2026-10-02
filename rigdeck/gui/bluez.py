"""`bluez` in QML: one shared view of Bluetooth adapters and devices for every page.

Pages filter `devices` by category (the Headset page shows Bluetooth headphones…), and the sidebar
uses `categories` to show pages whose only device is a Bluetooth one, and the Bluetooth entry
only while something is connected.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from .. import bluez
from .bridge import run_async

POLL_MS = 5000


class BluezWatcher(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._adapters: list[dict] = []
        self._devices: list[dict] = []
        self._reading = False
        QTimer(self, interval=POLL_MS, timeout=self.refresh).start()
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading:
            return
        self._reading = True

        def got(r):
            self._reading = False
            if r != (self._adapters, self._devices):
                self._adapters, self._devices = r
                self.changed.emit()

        def failed(e):
            self._reading = False
        run_async(bluez.read, got, failed)

    adapters = Property("QVariantList", lambda self: self._adapters, notify=changed)
    devices = Property("QVariantList", lambda self: self._devices, notify=changed)

    @Property("QVariantList", notify=changed)
    def categories(self):
        """Categories with a connected device, e.g. ['headset']."""
        return sorted({d["category"] for d in self._devices if d["connected"]})

    @Property(int, notify=changed)
    def connectedCount(self):
        return sum(1 for d in self._devices if d["connected"])

    canOpenSettings = Property(bool, lambda self: bluez.settings_command("bluetooth") is not None, constant=True)

    @Slot(str, bool)
    def setPowered(self, adapter_path, on):
        run_async(lambda: bluez.set_powered(adapter_path, on), lambda _: self.refresh(),
                  lambda e: self.toast.emit(f"Could not switch Bluetooth {'on' if on else 'off'}: {e}"))

    @Slot(str)
    def openSettings(self, page):
        cmd = bluez.settings_command(page)
        if cmd:
            QProcess.startDetached(cmd[0], cmd[1:])

    @Property("QVariantList", notify=changed)
    def summaries(self):
        return self.rows()

    def rows(self) -> list[dict]:
        """Overview rows: each connected device, with its battery."""
        rows = [{"id": d["category"] if d["category"] in ("headset", "mouse", "keyboard") else "bluetooth",
                 "icon": d["icon"], "title": d["name"], "detail": f"Bluetooth {d['kind'].lower()}",
                 "status": f"{d['battery']}% battery" if d["battery"] is not None else "Connected",
                 "connected": True, "tone": "live", "battery": d["battery"]}
                for d in self._devices if d["connected"]]
        return rows
