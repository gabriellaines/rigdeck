"""`app` in QML: navigation, preferences, background-service state and updates."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from .. import REPO, __version__, config, servicectl, updater
from .bridge import on_main, run_async


def prefs() -> dict:
    return config.section(config.load(), "app")


def save_pref(key: str, value):
    cfg = config.load()
    config.section(cfg, "app")[key] = value
    config.save(cfg)


class AppState(QObject):
    navChanged = Signal()
    serviceChanged = Signal()
    prefsChanged = Signal()
    updateChanged = Signal()
    toast = Signal(str)

    def __init__(self, theme, nav: list[dict]):
        super().__init__()
        self._theme = theme
        self._nav = nav
        p = prefs()
        self._reduce_motion = bool(p.get("reduce_motion", False))
        self._check_updates = bool(p.get("check_updates", True))
        self._service = "unknown"
        self._update = {"state": "idle", "current": __version__, "latest": "", "url": "",
                        "notes": "", "method": updater.install_method(), "log": "", "error": ""}
        self._svc_timer = QTimer(self, interval=5000, timeout=self.refreshService)
        self._svc_timer.start()
        self.refreshService()
        if self._check_updates:
            QTimer.singleShot(1500, lambda: self.checkUpdates(True))

    # ---- navigation
    nav = Property("QVariantList", lambda self: self._nav, notify=navChanged)
    version = Property(str, lambda self: __version__, constant=True)
    repoUrl = Property(str, lambda self: f"https://github.com/{REPO}", constant=True)

    # ---- preferences
    def _get_rm(self):
        return self._reduce_motion

    def _set_rm(self, v):
        if v != self._reduce_motion:
            self._reduce_motion = bool(v)
            save_pref("reduce_motion", self._reduce_motion)
            self.prefsChanged.emit()

    reduceMotion = Property(bool, _get_rm, _set_rm, notify=prefsChanged)

    def _get_cu(self):
        return self._check_updates

    def _set_cu(self, v):
        if v != self._check_updates:
            self._check_updates = bool(v)
            save_pref("check_updates", self._check_updates)
            self.prefsChanged.emit()

    checkUpdatesOnStart = Property(bool, _get_cu, _set_cu, notify=prefsChanged)

    @Slot(str)
    def setThemeMode(self, mode):
        self._theme.mode = mode
        save_pref("theme", mode)

    @Slot(str)
    def openUrl(self, url):
        QDesktopServices.openUrl(QUrl(url))

    # ---- background service
    serviceState = Property(str, lambda self: self._service, notify=serviceChanged)

    @Slot()
    def refreshService(self):
        def got(state):
            if state != self._service:
                self._service = state
                self.serviceChanged.emit()
        run_async(servicectl.state, got)

    @Slot()
    def startService(self):
        def done(ok):
            self.toast.emit("Service started" if ok else "Could not start the service — is rigdeck installed?")
            self.refreshService()
        run_async(servicectl.enable_now, done)

    # ---- updates
    update = Property("QVariantMap", lambda self: self._update, notify=updateChanged)

    def _set_update(self, **kw):
        self._update = {**self._update, **kw}
        self.updateChanged.emit()

    @Slot()
    def checkUpdates(self, quiet: bool = False):
        self._set_update(state="checking", error="")

        def done(rel):
            self._release = rel
            self._set_update(state="available" if rel["newer"] else "current", latest=rel["version"],
                             url=rel["url"] or "", notes=rel["notes"], method=rel["method"])

        def failed(e):
            self._set_update(state="error" if not quiet else "idle", error=str(e))
        run_async(updater.check, done, failed)

    @Slot()
    def applyUpdate(self):
        if self._update["state"] != "available":
            return
        self._set_update(state="updating", log="")

        def log(line):
            on_main(lambda: self._set_update(log=(self._update["log"] + line + "\n")[-4000:]))

        run_async(lambda: updater.apply(self._release, log),
                  lambda _: self._set_update(state="updated"),
                  lambda e: self._set_update(state="error", error=str(e)))

    @Slot()
    def restartApp(self):
        exe = os.path.join(os.path.dirname(sys.argv[0]), "rigdeck-gui")
        QProcess.startDetached(exe if os.path.exists(exe) else "rigdeck-gui", [])
        QGuiApplication.quit()
