"""`headset` in QML: battery and settings through HeadsetControl."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...gui.activity import AdaptiveTimer
from ...gui.bridge import run_async
from . import change, hc, saved

POLL_PAGE_MS = 3000      # while the Headset page is open: notice on/off quickly
POLL_MS = 15000          # otherwise (Overview battery)


class HeadsetBackend(QObject):
    stateChanged = Signal()
    settingsChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._status = "loading"  # loading | ok | off | none | not-installed | error
        self._error = ""
        self._st: dict = {}
        self._settings = saved()
        self._polling = False
        self._busy = False
        self._timer = AdaptiveTimer(self, self.refresh, page="headset", page_ms=POLL_PAGE_MS, visible_ms=POLL_MS)
        self.refresh()

    # ---- polling ---------------------------------------------------------------------

    @Slot()
    def refresh(self):
        if self._polling:
            return
        self._polling = True

        def got(st):
            self._polling = False
            self._st = st or {}
            self._status = "none" if st is None else "ok" if st["on"] else "off"
            self._error = ""
            self.stateChanged.emit()

        def failed(e):
            self._polling = False
            self._status = "not-installed" if isinstance(e, hc.NotInstalled) else "error"
            self._error = str(e)
            self.stateChanged.emit()
        run_async(hc.status, got, failed)

    status = Property(str, lambda self: self._status, notify=stateChanged)
    error = Property(str, lambda self: self._error, notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)

    @Property("QVariantMap", notify=stateChanged)
    def info(self):
        s = self._st
        return {"name": s.get("name", ""), "id": s.get("id", ""), "battery": s.get("battery"),
                "charging": bool(s.get("charging")), "caps": s.get("caps", []),
                "sidetoneOnOff": bool(s.get("sidetone_on_off")), "chatmix": s.get("chatmix"),
                "inactiveMax": s.get("inactive_max", 90)}

    @Property("QVariantMap", notify=stateChanged)
    def summary(self):
        """One line for the Overview's device list."""
        s, st = self._st, self._status
        status = {"ok": "Connected", "off": "Off", "none": "Not found", "loading": "…",
                  "not-installed": "Needs HeadsetControl", "error": "Error"}[st]
        if st == "ok" and s.get("battery") is not None:
            status = f"{s['battery']}% battery" + (" · charging" if s.get("charging") else "")
        return {"id": "headset", "icon": "headphones", "title": s.get("name") or "Headset",
                "detail": f"USB {s['id']}" if s.get("id") else "via HeadsetControl",
                "status": status, "connected": st == "ok",
                "tone": "live" if st == "ok" else "warning" if st in ("off", "loading") else "error",
                "battery": s.get("battery") if st == "ok" else None}

    # ---- settings --------------------------------------------------------------------

    # -1 = never set from RigDeck (HeadsetControl can't read the headset's current value)
    settings = Property("QVariantMap", lambda self: {k: self._settings.get(k, -1) for k in
                        ("sidetone", "inactive_time", "lights", "voice_prompts", "rotate_to_mute")},
                        notify=settingsChanged)

    @Slot(str, int)
    def set(self, key, value):
        if self._busy:
            return
        self._busy = True
        self.stateChanged.emit()

        def done(_):
            self._busy = False
            self._settings[key] = int(value)
            self.settingsChanged.emit()
            self.stateChanged.emit()

        def failed(e):
            self._busy = False
            self.stateChanged.emit()
            self.settingsChanged.emit()  # put the control back where it was
            self.toast.emit(f"Could not change the headset: {e}")
            self.refresh()
        run_async(lambda: change({key: value}), done, failed)
