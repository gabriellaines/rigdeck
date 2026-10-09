"""Qt application setup: theme, icons, backends, navigation, main window."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .. import APP_ID, __version__, config
from ..modules import MODULES
from . import bridge
from .appstate import AppState, prefs
from .bluez import BluezWatcher
from .customtheme import CustomThemes
from .resources import ResourceMonitor
from .setupfile import SettingsFile
from .icons import IconProvider
from .system import SystemBackend
from .theme import Theme

QML_DIR = os.path.join(os.path.dirname(__file__), "qml")


def _navigation(ctx, keep: list, peripherals: list) -> list[dict]:
    """Sidebar entries from modules: detected devices (or ones seen before) and system pages.
    Peripheral backends are also collected into `peripherals` for the Overview's device list."""
    cfg = config.load()
    app_cfg = config.section(cfg, "app")
    seen = set(app_cfg.get("seen_devices", []))
    nav = []
    for m in sorted(MODULES, key=lambda m: m.order):
        page = m.qml_page()
        if not page:
            continue
        present = m.detect()
        pluggable = m.kind in ("device", "peripheral")
        # static: always in the sidebar; otherwise only while a matching Bluetooth device is connected
        static = (present or m.id in seen) if pluggable else (present if m.bluetooth == ("*",) else True)
        if not static and not m.bluetooth:
            continue
        if pluggable and present and m.id not in seen:
            seen.add(m.id)
            app_cfg["seen_devices"] = sorted(seen)
            config.save(cfg)
        backend = m.qt_backend(ctx)
        if backend is not None:
            keep.append(backend)
            ctx.setContextProperty(m.id, backend)
            if hasattr(backend, "summary") or hasattr(backend, "summaries"):
                peripherals.append(backend)          # rows in the Overview's device list
        nav.append({"id": m.id, "title": m.title, "icon": m.icon, "kind": m.kind, "static": static,
                    "bt": list(m.bluetooth), "page": QUrl.fromLocalFile(page).toString()})
    return nav


def run(argv: list[str]) -> int:
    start_page = ""
    if "--page" in argv:  # rigdeck-gui --page cooler
        i = argv.index("--page")
        start_page = argv[i + 1] if i + 1 < len(argv) else ""
        del argv[i:i + 2]

    QQuickStyle.setStyle("Fusion")  # neutral base; colors come from the theme palette
    app = QGuiApplication(argv)
    app.setApplicationName("rigdeck")
    app.setApplicationDisplayName("RigDeck")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(QIcon.fromTheme(APP_ID))
    bridge.init()

    theme = Theme(prefs().get("theme", "system"))
    engine = QQmlApplicationEngine()
    engine.addImageProvider("icons", IconProvider())
    engine.addImportPath(QML_DIR)
    ctx = engine.rootContext()
    keep: list = [theme]
    system = SystemBackend()
    keep.append(system)
    ctx.setContextProperty("theme", theme)
    custom_themes = CustomThemes(theme)      # import / save-template / remove a person's own themes
    keep.append(custom_themes)
    ctx.setContextProperty("customThemes", custom_themes)
    ctx.setContextProperty("system", system)
    monitor = ResourceMonitor()  # a minute of CPU / memory / disk / network / GPU history
    keep.append(monitor)
    ctx.setContextProperty("usage", monitor)   # not "resources" (every QML item has one) nor "monitor" (the Monitors module)
    bluez = BluezWatcher()       # shared by the Bluetooth page, category pages and the sidebar
    keep.append(bluez)
    ctx.setContextProperty("bluez", bluez)
    peripherals: list = []
    nav = _navigation(ctx, keep, peripherals)
    state = AppState(theme, nav, peripherals + [bluez])
    keep.append(state)
    ctx.setContextProperty("appState", state)
    settings_file = SettingsFile(ctx)        # import / export every device's settings
    keep.append(settings_file)
    ctx.setContextProperty("settingsFile", settings_file)
    ctx.setContextProperty("startPage", start_page)

    engine.load(QUrl.fromLocalFile(os.path.join(QML_DIR, "Main.qml")))
    if not engine.rootObjects():
        return 1
    app._keep = keep  # backends must outlive the QML engine
    return app.exec()
