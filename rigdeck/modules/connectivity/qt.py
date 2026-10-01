"""`connectivity` in QML: network and Bluetooth status, Bluetooth on/off, desktop settings."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from ...gui.bridge import run_async
from . import read, set_bluetooth_power, settings_command

POLL_MS = 5000


def _wifi_icon(signal):
    return "wifi-off" if signal is None else "wifi" if signal >= 67 else "wifi-high" if signal >= 34 else "wifi-low"


class ConnectivityBackend(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._s: dict = {"network": [], "adapters": [], "bluetooth": [], "error": "", "nmcli": True}
        self._loaded = False
        self._reading = False
        self._timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        self._timer.start()
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading:
            return
        self._reading = True

        def got(s):
            self._reading, self._loaded, self._s = False, True, s
            self.changed.emit()

        def failed(e):
            self._reading = False
            self._s = {**self._s, "error": str(e)}
            self.changed.emit()
        run_async(read, got, failed)

    state = Property("QVariantMap", lambda self: self._s, notify=changed)
    loaded = Property(bool, lambda self: self._loaded, notify=changed)
    canOpenSettings = Property(bool, lambda self: settings_command("bluetooth") is not None, constant=True)

    @Property("QVariantList", notify=changed)
    def summaries(self):
        """Overview rows: Wi-Fi, each Bluetooth adapter, and each connected Bluetooth device."""
        rows = []
        for d in self._s["network"]:
            if d["type"] != "wifi":
                continue
            w = d.get("wifi") or {}
            rows.append({"id": "connectivity", "icon": _wifi_icon(w.get("signal")), "title": d["hardware"] or "Wi-Fi",
                         "detail": f"{w['ssid']} · {w['band']}" if w else d["device"],
                         "status": f"{w['signal']}% signal" if w.get("signal") is not None else d["state"].capitalize(),
                         "connected": d["state"] == "connected", "tone": "live" if w else "warning"})
        for a in self._s["adapters"]:
            n = sum(1 for d in self._s["bluetooth"] if d["connected"])
            rows.append({"id": "connectivity", "icon": "bluetooth" if a["powered"] else "bluetooth-off",
                         "title": a["hardware"] or "Bluetooth",
                         "detail": "Bluetooth" + (f" · {n} connected" if n else ""),
                         "status": "On" if a["powered"] else "Off", "connected": a["powered"],
                         "tone": "live" if a["powered"] else "warning"})
        for d in self._s["bluetooth"]:
            if d["connected"]:
                rows.append({"id": "connectivity", "icon": "bluetooth", "title": d["name"], "detail": "Bluetooth",
                             "status": f"{d['battery']}% battery" if d["battery"] is not None else "Connected",
                             "connected": True, "tone": "live"})
        return rows

    @Property("QVariantMap", notify=changed)
    def summary(self):
        rows = self.summaries
        return rows[0] if rows else {"id": "connectivity", "icon": "wifi", "title": "Wi-Fi & Bluetooth",
                                     "detail": "", "status": "…", "connected": False, "tone": "warning"}

    @Slot(str, bool)
    def setBluetooth(self, adapter_path, on):
        run_async(lambda: set_bluetooth_power(adapter_path, on), lambda _: self.refresh(),
                  lambda e: self.toast.emit(f"Could not switch Bluetooth {'on' if on else 'off'}: {e}"))

    @Slot(str)
    def openSettings(self, page):
        cmd = settings_command(page)
        if cmd:
            QProcess.startDetached(cmd[0], cmd[1:])
