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
from .icons import IconProvider
from .system import SystemBackend
from .theme import Theme

QML_DIR = os.path.join(os.path.dirname(__file__), "qml")


def _navigation(ctx, keep: list) -> list[dict]:
    """Sidebar entries from modules: detected devices (or ones seen before) and system pages."""
    cfg = config.load()
    app_cfg = config.section(cfg, "app")
    seen = set(app_cfg.get("seen_devices", []))
    nav = []
    for m in sorted(MODULES, key=lambda m: m.order):
        page = m.qml_page()
        if not page:
            continue
        present = m.detect()
        if m.kind == "device" and not present and m.id not in seen:
            continue
        if m.kind == "device" and present and m.id not in seen:
            seen.add(m.id)
            app_cfg["seen_devices"] = sorted(seen)
            config.save(cfg)
        backend = m.qt_backend(ctx)
        if backend is not None:
            keep.append(backend)
            ctx.setContextProperty(m.id, backend)
        nav.append({"id": m.id, "title": m.title, "icon": m.icon, "kind": m.kind,
                    "page": QUrl.fromLocalFile(page).toString()})
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
    ctx.setContextProperty("system", system)
    nav = _navigation(ctx, keep)
    state = AppState(theme, nav)
    keep.append(state)
    ctx.setContextProperty("appState", state)
    ctx.setContextProperty("startPage", start_page)

    engine.load(QUrl.fromLocalFile(os.path.join(QML_DIR, "Main.qml")))
    if not engine.rootObjects():
        return 1
    app._keep = keep  # backends must outlive the QML engine
    return app.exec()
