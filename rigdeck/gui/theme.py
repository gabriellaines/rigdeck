"""Design tokens from the RigDeck interface spec, plus a few extra themes, plus a person's own.

"system" follows the OS light/dark setting using RigDeck's own Breeze-style light and dark
themes; the other names below are themes picked directly in Settings. A person can also add
their own, as a JSON file imported through Settings — see rigdeck.customtheme and
docs/custom-themes.md. Those are kept as `"custom:<slug>"` mode values, so they can never
collide with a built-in name.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from .. import customtheme
from ..customtheme import TOKEN_KEYS

# OKLCH values from the spec, converted to sRGB, plus a few popular editor palettes.
THEMES = {
    "light": {"label": "Light", "dark": False,
              "window": "#f1f4f6", "panel": "#fcfdff", "raised": "#e2e7ec", "text": "#1f2329",
              "muted": "#646d76", "border": "#c2c8cf", "accent": "#0f88dd"},
    "dark": {"label": "Dark", "dark": True,
             "window": "#101214", "panel": "#1c1e21", "raised": "#282c2f", "text": "#e2e5e8",
             "muted": "#90969c", "border": "#3a3e42", "accent": "#42a1f3"},
    "solarized": {"label": "Solarized Light", "dark": False,
                  "window": "#eee8d5", "panel": "#fdf6e3", "raised": "#e4dcc3", "text": "#586e75",
                  "muted": "#93a1a1", "border": "#d3cbb7", "accent": "#268bd2"},
    "dracula": {"label": "Dracula", "dark": True,
                "window": "#282a36", "panel": "#2b2e3b", "raised": "#383a4a", "text": "#f8f8f2",
                "muted": "#6272a4", "border": "#44475a", "accent": "#bd93f9"},
    "one-dark": {"label": "One Dark", "dark": True,
                 "window": "#282c34", "panel": "#2c313a", "raised": "#353b45", "text": "#abb2bf",
                 "muted": "#5c6370", "border": "#3b4048", "accent": "#61afef"},
}
SHARED = {"live": "#00978a", "warning": "#e49e22", "error": "#e24947", "onAccent": "#ffffff"}
# "system" follows the OS; the built-in names are picked directly; "custom:<slug>" is a person's own.
MODES = ("system",) + tuple(THEMES)


class Theme(QObject):
    changed = Signal()

    def __init__(self, mode: str = "system"):
        super().__init__()
        self._custom = customtheme.list_themes()
        self._mode = mode if self._valid(mode) else "system"
        QGuiApplication.styleHints().colorSchemeChanged.connect(lambda *_: self._apply())
        self._apply()

    def _valid(self, mode: str) -> bool:
        return mode in MODES or (mode.startswith("custom:") and mode[7:] in self._custom)

    def _system_dark(self) -> bool:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark

    def _resolve(self, mode: str) -> dict | None:
        if mode.startswith("custom:"):
            return self._custom.get(mode[7:])
        key = ("dark" if self._system_dark() else "light") if mode == "system" else mode
        return THEMES.get(key)

    def _apply(self):
        theme = self._resolve(self._mode)
        if theme is None:  # the active custom theme's file disappeared
            self._mode = "system"
            theme = self._resolve(self._mode)
        self._dark = theme["dark"]
        self._t = {**{k: theme[k] for k in TOKEN_KEYS}, **SHARED}
        self._update_palette()
        self.changed.emit()

    def reload_custom(self):
        """Re-scan ~/.config/rigdeck/themes/ after one is added, edited or removed."""
        self._custom = customtheme.list_themes()
        self._apply()

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
        if mode != self._mode and self._valid(mode):
            self._mode = mode
            self._apply()

    mode = Property(str, _get_mode, _set_mode, notify=changed)
    # Selectable themes in display order, each {value, label}; "system" is added by the QML side.
    themes = Property("QVariantList",
                       lambda self: [{"value": k, "label": v["label"]} for k, v in THEMES.items()]
                                    + [{"value": f"custom:{slug}", "label": t["name"]}
                                       for slug, t in self._custom.items()],
                       notify=changed)
    # A person's own themes, for the "Your themes" management list ({slug, name} — no "custom:" prefix).
    customThemes = Property("QVariantList",
                             lambda self: [{"slug": slug, "name": t["name"]}
                                           for slug, t in self._custom.items()],
                             notify=changed)
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

    def tokens(self) -> dict:
        """The 7 color tokens of the active theme, as hex strings — used to build a theme template."""
        return {k: self._t[k] for k in TOKEN_KEYS}
