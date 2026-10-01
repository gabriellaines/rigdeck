"""Design tokens from the RigDeck interface spec, following the system dark/light setting."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette

# OKLCH values from the spec, converted to sRGB.
TOKENS = {
    "dark": {"window": "#101214", "panel": "#1c1e21", "raised": "#282c2f", "text": "#e2e5e8",
             "muted": "#90969c", "border": "#3a3e42", "accent": "#42a1f3"},
    "light": {"window": "#f1f4f6", "panel": "#fcfdff", "raised": "#e2e7ec", "text": "#1f2329",
              "muted": "#646d76", "border": "#c2c8cf", "accent": "#0f88dd"},
}
SHARED = {"live": "#00978a", "warning": "#e49e22", "error": "#e24947", "onAccent": "#ffffff"}
MODES = ("system", "light", "dark")


class Theme(QObject):
    changed = Signal()

    def __init__(self, mode: str = "system"):
        super().__init__()
        self._mode = mode if mode in MODES else "system"
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda *_: self._apply())
        self._apply()

    def _system_dark(self) -> bool:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def _apply(self):
        dark = self._mode == "dark" or (self._mode == "system" and self._system_dark())
        self._dark = dark
        self._t = {**TOKENS["dark" if dark else "light"], **SHARED}
        self._update_palette()
        self.changed.emit()

    def _update_palette(self):
        """Give native Qt controls (Fusion style) the same colors."""
        t = {k: QColor(v) for k, v in self._t.items()}
        p = QPalette()
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            p.setColor(group, QPalette.ColorRole.Window, t["window"])
            p.setColor(group, QPalette.ColorRole.WindowText, t["text"])
            p.setColor(group, QPalette.ColorRole.Base, t["panel"])
            p.setColor(group, QPalette.ColorRole.AlternateBase, t["raised"])
            p.setColor(group, QPalette.ColorRole.Text, t["text"])
            p.setColor(group, QPalette.ColorRole.Button, t["raised"])
            p.setColor(group, QPalette.ColorRole.ButtonText, t["text"])
            p.setColor(group, QPalette.ColorRole.Highlight, t["accent"])
            p.setColor(group, QPalette.ColorRole.HighlightedText, t["onAccent"])
            p.setColor(group, QPalette.ColorRole.ToolTipBase, t["raised"])
            p.setColor(group, QPalette.ColorRole.ToolTipText, t["text"])
            p.setColor(group, QPalette.ColorRole.PlaceholderText, t["muted"])
            p.setColor(group, QPalette.ColorRole.Mid, t["border"])
            p.setColor(group, QPalette.ColorRole.Light, t["raised"])
            p.setColor(group, QPalette.ColorRole.Dark, t["border"])
        dis = QPalette.ColorGroup.Disabled
        for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            p.setColor(dis, role, t["muted"])
        for role, key in ((QPalette.ColorRole.Window, "window"), (QPalette.ColorRole.Base, "panel"),
                          (QPalette.ColorRole.Button, "raised")):
            p.setColor(dis, role, t[key])
        QGuiApplication.setPalette(p)

    # ---- QML properties
    def _get_mode(self):
        return self._mode

    def _set_mode(self, mode):
        if mode in MODES and mode != self._mode:
            self._mode = mode
            self._apply()

    mode = Property(str, _get_mode, _set_mode, notify=changed)
    dark = Property(bool, lambda self: self._dark, notify=changed)
    window = Property(QColor, lambda self: QColor(self._t["window"]), notify=changed)
    panel = Property(QColor, lambda self: QColor(self._t["panel"]), notify=changed)
    raised = Property(QColor, lambda self: QColor(self._t["raised"]), notify=changed)
    text = Property(QColor, lambda self: QColor(self._t["text"]), notify=changed)
    muted = Property(QColor, lambda self: QColor(self._t["muted"]), notify=changed)
    border = Property(QColor, lambda self: QColor(self._t["border"]), notify=changed)
    accent = Property(QColor, lambda self: QColor(self._t["accent"]), notify=changed)
    onAccent = Property(QColor, lambda self: QColor(self._t["onAccent"]), notify=changed)
    live = Property(QColor, lambda self: QColor(self._t["live"]), notify=changed)
    warning = Property(QColor, lambda self: QColor(self._t["warning"]), notify=changed)
    error = Property(QColor, lambda self: QColor(self._t["error"]), notify=changed)
    radius = Property(int, lambda self: 6, constant=True)
