"""Run hardware calls off the UI thread and hand results back to Qt's main thread."""
from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import QObject, Qt, Signal


class _Invoker(QObject):
    call = Signal(object)

    def __init__(self):
        super().__init__()
        self.call.connect(lambda fn: fn(), Qt.ConnectionType.QueuedConnection)


_invoker: _Invoker | None = None


def init():
    """Create the invoker on the main thread (call once at startup)."""
    global _invoker
    _invoker = _Invoker()


def on_main(fn):
    _invoker.call.emit(fn)


def run_async(fn, done=None, error=None):
    """fn() on a worker thread; done(result) / error(exc) back on the main thread."""
    def work():
        try:
            result = fn()
        except Exception as e:  # noqa: BLE001 — reported to the UI
            if error:
                on_main(lambda: error(e))
            else:
                traceback.print_exc()
            return
        if done:
            on_main(lambda: done(result))

    threading.Thread(target=work, daemon=True).start()
