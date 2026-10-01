"""`webcam` in QML: camera list, grouped controls, live changes (coalesced) and reset."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from ...gui.bridge import run_async
from . import change, describe, reset, saved, v4l2

POLL_MS = 3000


class WebcamBackend(QObject):
    camerasChanged = Signal()
    controlsChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._cams: list[dict] = []
        self._index = 0
        self._groups: list = []
        self._saved: dict = {}
        self._error = ""
        self._pending: dict = {}    # changes waiting for the camera
        self._writing = False
        self._reading = False
        self._timer = QTimer(self, interval=POLL_MS, timeout=self.refresh)
        self._timer.start()
        self.refresh()

    # ---- cameras and controls ----------------------------------------------------------

    def _by_id(self) -> str | None:
        return self._cams[self._index]["byId"] if self._index < len(self._cams) else None

    @Slot()
    def refresh(self):
        if self._reading or self._writing:
            return
        self._reading = True

        def read():
            cams = []
            for by_id in v4l2.cameras():
                try:
                    with v4l2.Camera(by_id) as c:
                        cams.append({"byId": by_id, "name": c.name, "path": c.path})
                except v4l2.WebcamError as e:
                    cams.append({"byId": by_id, "name": by_id, "path": "", "error": str(e)})
            groups, err = [], ""
            idx = min(self._index, max(0, len(cams) - 1))
            if cams and not cams[idx].get("error"):
                try:
                    with v4l2.Camera(cams[idx]["byId"]) as c:
                        groups = describe(c.controls())
                except (v4l2.WebcamError, OSError) as e:
                    err = str(e)
            elif cams:
                err = cams[idx]["error"]
            return cams, idx, groups, err, saved(cams[idx]["byId"]) if cams else {}

        def got(r):
            self._reading = False
            cams, idx, groups, err, sv = r
            if cams != self._cams or idx != self._index:
                self._cams, self._index = cams, idx
                self.camerasChanged.emit()
            if not self._pending:  # don't yank a slider the user is still moving
                self._groups, self._error, self._saved = groups, err, sv
                self.controlsChanged.emit()

        def failed(e):
            self._reading = False
            self._error = str(e)
            self.controlsChanged.emit()
        run_async(read, got, failed)

    cameras = Property("QVariantList", lambda self: self._cams, notify=camerasChanged)
    index = Property(int, lambda self: self._index, notify=camerasChanged)
    groups = Property("QVariantList", lambda self: self._groups, notify=controlsChanged)
    error = Property(str, lambda self: self._error, notify=controlsChanged)
    savedKeys = Property("QVariantList", lambda self: list(self._saved), notify=controlsChanged)

    @Property(str, notify=camerasChanged)
    def name(self):
        return self._cams[self._index]["name"] if self._cams else ""

    @Property("QVariantMap", notify=camerasChanged)
    def summary(self):
        cam = self._cams[self._index] if self._cams else None
        n = len(self._cams)
        return {"id": "webcam", "icon": "webcam", "title": cam["name"] if cam else "Webcam",
                "detail": cam["path"] + (f" · {n} cameras" if n > 1 else "") if cam else "",
                "status": "Connected" if cam else "Not connected", "connected": bool(cam),
                "tone": "live" if cam else "warning", "battery": None}

    @Slot(int)
    def select(self, i):
        if 0 <= i < len(self._cams) and i != self._index:
            self._index = i
            self.camerasChanged.emit()
            self.refresh()

    # ---- changes -------------------------------------------------------------------------

    @Slot(str, int)
    def set(self, key, value):
        """Queue a change; while one is being written, later ones for the same control replace it."""
        self._pending[key] = int(value)
        self._flush()

    def _flush(self):
        by_id = self._by_id()
        if self._writing or not self._pending or not by_id:
            return
        batch, self._pending = self._pending, {}
        self._writing = True

        def done(failed):
            self._writing = False
            if failed:
                self.toast.emit("The camera didn't accept: " + ", ".join(failed))
            if self._pending:
                self._flush()
            else:
                self.refresh()  # switches change which controls are active

        def error(e):
            self._writing = False
            self._pending.clear()
            self.toast.emit(f"Could not change the camera: {e}")
            self.refresh()
        run_async(lambda: change(by_id, batch), done, error)

    @Slot()
    def resetDefaults(self):
        by_id = self._by_id()
        if not by_id:
            return
        self._pending.clear()
        run_async(lambda: reset(by_id), lambda _: (self.toast.emit("Camera back to its default settings"),
                                                   self.refresh()),
                  lambda e: self.toast.emit(f"Could not reset the camera: {e}"))
