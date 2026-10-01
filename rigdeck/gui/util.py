"""Small helpers shared by GUI pages."""
from __future__ import annotations

import threading
import traceback

from gi.repository import GLib


def run_async(fn, on_done=None, on_error=None):
    """Run fn() on a worker thread; deliver the result (or exception) on the GTK main loop.

    Hardware calls can take tens of milliseconds, so they never run on the UI thread.
    """
    def worker():
        try:
            result = fn()
        except Exception as e:  # noqa: BLE001 — reported to the UI
            if on_error:
                GLib.idle_add(on_error, e)
            else:
                traceback.print_exc()
            return
        if on_done:
            GLib.idle_add(on_done, result)

    threading.Thread(target=worker, daemon=True).start()


class Debounce:
    """Call fn only after `ms` of quiet — for sliders and colour pickers."""

    def __init__(self, ms: int, fn):
        self.ms, self.fn, self.source = ms, fn, 0

    def __call__(self, *args):
        if self.source:
            GLib.source_remove(self.source)
        self.source = GLib.timeout_add(self.ms, self._fire, args)

    def _fire(self, args):
        self.source = 0
        self.fn(*args)
        return GLib.SOURCE_REMOVE
