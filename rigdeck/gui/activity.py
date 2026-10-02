"""What the user is looking at — whether the window is visible, and which page — so backends poll
only as much as that needs. A minimised or hidden RigDeck polls nothing (the service keeps
doing its own work).

    AdaptiveTimer(owner, fn, page="mouse", page_ms=10000, visible_ms=60000)

polls every 10 s while the Mouse page is shown, every 60 s while the window shows another page,
and not at all while the window is hidden (hidden_ms=None). When polling resumes after a pause,
fn runs right away so the page isn't stale.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class Activity(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.visible = True
        self.page = "overview"

    def set(self, visible: bool, page: str):
        if (visible, page) != (self.visible, self.page):
            self.visible, self.page = visible, page
            self.changed.emit()


_activity: Activity | None = None


def activity() -> Activity:
    global _activity
    if _activity is None:
        _activity = Activity()
    return _activity


class AdaptiveTimer(QTimer):
    def __init__(self, owner: QObject, fn, *, page: str | None = None, page_ms: int | None = None,
                 visible_ms: int | None = None, hidden_ms: int | None = None, start_now: bool = False):
        super().__init__(owner)
        self.fn = fn
        self.page, self.page_ms, self.visible_ms, self.hidden_ms = page, page_ms, visible_ms, hidden_ms
        self.timeout.connect(fn)
        activity().changed.connect(self._update)
        self._update(initial=True)
        if start_now:
            fn()

    def _interval(self) -> int | None:
        a = activity()
        if not a.visible:
            return self.hidden_ms
        if self.page is not None and a.page == self.page and self.page_ms is not None:
            return self.page_ms
        return self.visible_ms

    def _update(self, initial: bool = False):
        ms = self._interval()
        if ms is None:
            self.stop()
            return
        was_running, old = self.isActive(), self.interval()
        self.setInterval(ms)
        if not was_running:
            self.start()
            if not initial:
                self.fn()          # resumed after a pause: refresh now
        elif ms < old and not initial:
            self.fn()              # e.g. its page just opened: don't wait for the slower tick
