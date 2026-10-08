"""`lighting` in QML: sync one colour to every device with lighting, and restore."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from ...gui.activity import AdaptiveTimer
from ...gui.bridge import run_async
from . import TARGETS, restore, status, sync

NAMES = {t.id: t.name for t in TARGETS}


class LightingBackend(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, ctx=None):
        super().__init__()
        self._ctx = ctx
        self._status = {"active": False, "color": "", "devices": []}
        self._busy = False
        self._reading = False
        # plugging a device in (or the service syncing it) shows up while the page is open
        AdaptiveTimer(self, self.refresh, page="lighting", page_ms=2000)
        self.refresh()

    @Slot()
    def refresh(self):
        if self._reading:
            return
        self._reading = True

        def got(s):
            self._reading = False
            if s != self._status:
                self._status = s
                self.changed.emit()

        def failed(_e):
            self._reading = False
        run_async(status, got, failed)

    status = Property("QVariantMap", lambda self: self._status, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)

    def _run(self, work, message):
        if self._busy:
            return
        self._busy = True
        self.changed.emit()

        def done(r):
            self._busy = False
            self.toast.emit(message(r))
            self.refresh()
            self._refresh_pages()

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not change the lighting: {e}")
            self.refresh()
        run_async(work, done, failed)

    @Slot(str, "QVariantList")
    def sync(self, color, only):
        def message(errors):
            if not errors:
                return f"#{color} on every device"
            return "Not changed: " + "; ".join(f"{NAMES[k]} ({v})" for k, v in errors.items())
        self._run(lambda: sync(color, list(only) or None), message)

    @Slot()
    def restore(self):
        def message(r):
            errors, notes = r
            if errors:
                return "Not restored: " + "; ".join(f"{NAMES[k]} ({v})" for k, v in errors.items())
            return "Every device is back to its own lighting" + (f" ({notes[0]})" if notes else "")
        self._run(restore, message)

    def _refresh_pages(self):
        """The device pages show what they last read; have them read the new lighting."""
        if self._ctx is None:
            return
        for page_id, method in (("cooler", "reloadLed"), ("motherboard", "refreshLighting"),
                                ("keyboard", "lightingChangedElsewhere"), ("mouse", "refresh")):
            backend = self._ctx.contextProperty(page_id)
            if backend is not None and hasattr(backend, method):
                getattr(backend, method)()
