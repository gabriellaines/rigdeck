"""Base class for content pages shown in the main window."""
from __future__ import annotations

from gi.repository import GLib, Gtk


class Page:
    """A page supplies `body` (the content) and optionally `title_widget` for the header bar.

    The window calls shown()/hidden() so pages only poll hardware while visible.
    """

    title = ""
    icon = "application-x-executable-symbolic"

    def __init__(self, window):
        self.window = window
        self.body: Gtk.Widget = Gtk.Box()
        self.title_widget: Gtk.Widget | None = None
        self._timer = 0

    def poll_every(self, seconds: float, fn):
        """Run fn now and then every `seconds` while the page is visible."""
        self._poll = (seconds, fn)

    def shown(self):
        if hasattr(self, "_poll") and not self._timer:
            seconds, fn = self._poll
            fn()
            self._timer = GLib.timeout_add(int(seconds * 1000), lambda: (fn(), GLib.SOURCE_CONTINUE)[1])

    def hidden(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
