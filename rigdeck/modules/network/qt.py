"""`network` in QML: adapters with addresses and live throughput, nearby Wi-Fi networks."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot

from ... import bluez
from ...gui.bridge import run_async
from . import counters, read

POLL_MS = 5000        # adapters, addresses, Wi-Fi list
RATE_MS = 1000        # throughput (two small sysfs reads per adapter)


def _wifi_icon(signal):
    return "wifi-off" if signal is None else "wifi" if signal >= 67 else "wifi-high" if signal >= 34 else "wifi-low"


class NetworkBackend(QObject):
    changed = Signal()
    ratesChanged = Signal()

    def __init__(self):
        super().__init__()
        self._s: dict = {"nmcli": True, "adapters": [], "networks": [], "internet": ""}
        self._rates: dict[str, dict] = {}
        self._last: dict[str, tuple] = {}
        self._loaded = False
        self._reading = False
        QTimer(self, interval=POLL_MS, timeout=self.refresh).start()
        QTimer(self, interval=RATE_MS, timeout=self._rate_tick).start()
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

    def _rate_tick(self):
        import time
        now = time.monotonic()
        rates = {}
        for a in self._s.get("adapters", []):
            dev = a["device"]
            rx, tx = counters(dev)
            if dev in self._last:
                t0, rx0, tx0 = self._last[dev]
                dt = max(now - t0, 0.001)
                rates[dev] = {"rx": max(0, rx - rx0) / dt, "tx": max(0, tx - tx0) / dt}
            self._last[dev] = (now, rx, tx)
        self._rates = rates
        self.ratesChanged.emit()

    state = Property("QVariantMap", lambda self: self._s, notify=changed)
    loaded = Property(bool, lambda self: self._loaded, notify=changed)
    rates = Property("QVariantMap", lambda self: self._rates, notify=ratesChanged)
    canOpenSettings = Property(bool, lambda self: bluez.settings_command("network") is not None, constant=True)

    @Slot()
    def openSettings(self):
        cmd = bluez.settings_command("network")
        if cmd:
            QProcess.startDetached(cmd[0], cmd[1:])

    @Property("QVariantList", notify=changed)
    def summaries(self):
        """Overview: the Wi-Fi adapters (Ethernet is part of the board)."""
        rows = []
        for a in self._s.get("adapters", []):
            if a["type"] != "wifi":
                continue
            w = a.get("wifi") or {}
            rows.append({"id": "network", "icon": _wifi_icon(w.get("signal")), "title": a["hardware"] or "Wi-Fi",
                         "detail": f"{w['ssid']} · {w['band']}" if w else "Not connected",
                         "status": f"{w['signal']}% signal" if w else a["state"].capitalize(),
                         "connected": bool(w), "tone": "live" if w else "warning"})
        return rows
