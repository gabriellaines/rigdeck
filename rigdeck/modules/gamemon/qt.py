"""`gamemon` in QML: start/stop a recording, follow it live, browse and review past sessions."""
from __future__ import annotations

import os

from PySide6.QtCore import Property, QObject, QStandardPaths, Signal, Slot

from ... import sessions
from ...gui.activity import AdaptiveTimer
from ...gui.bridge import run_async

LIVE_POINTS = 120        # live graphs: the last two minutes
GRAPH_POINTS = 600       # session graphs: at most this many points (averaged buckets)


def _downsample(values: list, n: int = GRAPH_POINTS) -> list:
    if len(values) <= n:
        return [0 if v is None else v for v in values]
    out, size = [], len(values) / n
    for i in range(n):
        chunk = [v for v in values[int(i * size):int((i + 1) * size)] if v is not None]
        out.append(round(sum(chunk) / len(chunk), 2) if chunk else 0)
    return out


def _series(samples: list[dict], n: int) -> dict:
    out = {k: _downsample([s.get(k) for s in samples], n) for k in sessions.METRICS}
    disks = sorted({d for s in samples for d in s.get("disks", {})})
    for d in disks:
        rows = [s.get("disks", {}).get(d, {}) for s in samples]
        out[f"{d}:temp"] = _downsample([r.get("temp") for r in rows], n)
        out[f"{d}:io"] = _downsample([(r.get("r") or 0) + (r.get("w") or 0) for r in rows], n)
    return out


class GameMonitorBackend(QObject):
    stateChanged = Signal()
    sessionsChanged = Signal()
    detailChanged = Signal()
    toast = Signal(str)

    def __init__(self):
        super().__init__()
        self._rec: dict | None = None
        self._live: dict = {}
        self._list: list = []
        self._detail: dict = {}
        self._busy = False
        self._mh = sessions.mangohud_state()
        AdaptiveTimer(self, self.refresh, page="gamemon", page_ms=1000, visible_ms=5000)
        self.refresh()
        self.refreshList()

    # ---- live recording ------------------------------------------------------------------

    @Slot()
    def refresh(self):
        def read():
            st = sessions.recording()
            samples = sessions.load_samples(st["id"])[-LIVE_POINTS:] if st else []
            return st, samples

        def got(r):
            st, samples = r
            was = self._rec
            self._rec = st
            self._live = {"last": samples[-1] if samples else {}, "elapsed": samples[-1]["t"] if samples else 0,
                          "series": _series(samples, LIVE_POINTS)} if st else {}
            self.stateChanged.emit()
            if bool(was) != bool(st):
                self.refreshList()
        run_async(read, got)

    recording = Property(bool, lambda self: self._rec is not None, notify=stateChanged)
    live = Property("QVariantMap", lambda self: self._live, notify=stateChanged)
    busy = Property(bool, lambda self: self._busy, notify=stateChanged)
    metrics = Property("QVariantMap", lambda self: {k: {"label": l, "unit": u} for k, (l, u) in sessions.METRICS.items()},
                       constant=True)

    @Slot(str)
    def start(self, name):
        if self._busy or self._rec:
            return
        self._busy = True
        self.stateChanged.emit()

        def done(_):
            self._busy = False
            self.refresh()

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not start recording: {e}")
            self.stateChanged.emit()
        run_async(lambda: sessions.start_background(name.strip()), done, failed)

    @Slot()
    def stop(self):
        if self._busy or not self._rec:
            return
        self._busy = True
        self.stateChanged.emit()

        def done(sid):
            self._busy = False
            self.refresh()
            self.refreshList()
            if sid:
                self.select(sid)
                self.toast.emit("Session saved")

        def failed(e):
            self._busy = False
            self.toast.emit(f"Could not stop recording: {e}")
            self.stateChanged.emit()
        run_async(sessions.stop, done, failed)

    # ---- past sessions -------------------------------------------------------------------

    @Slot()
    def refreshList(self):
        def got(rows):
            self._list = rows
            self.sessionsChanged.emit()
            if not self._detail:                     # open the newest finished session
                newest = next((r for r in rows if r["finished"]), None)
                if newest:
                    self.select(newest["id"])
        run_async(sessions.list_sessions, got)

    sessionList = Property("QVariantList", lambda self: self._list, notify=sessionsChanged)
    detail = Property("QVariantMap", lambda self: self._detail, notify=detailChanged)

    @Slot(str)
    def select(self, sid):
        def read():
            d = sessions.details(sid)
            n = len(d["samples"])
            dur = d["summary"].get("duration") or 0
            away = [{**a, "from": a["start"] / dur, "to_": a["end"] / dur} for a in d["away"]] if dur else []
            return {"id": sid, "meta": d["meta"], "summary": d["summary"], "frames": d["frames"], "away": away,
                    "series": _series(d["samples"], GRAPH_POINTS), "points": min(n, GRAPH_POINTS)}

        def got(d):
            self._detail = d
            self.detailChanged.emit()
        run_async(read, got, lambda e: self.toast.emit(f"Could not open the session: {e}"))

    @Slot(str)
    def remove(self, sid):
        sessions.delete(sid)
        if self._detail.get("id") == sid:
            self._detail = {}
            self.detailChanged.emit()
        self.refreshList()

    @Slot(str)
    def exportCsv(self, sid):
        folder = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or os.path.expanduser("~")
        path = os.path.join(folder, f"rigdeck-session-{sid}.csv")
        run_async(lambda: sessions.export_csv(sid, path), lambda p: self.toast.emit(f"Saved {p}"),
                  lambda e: self.toast.emit(f"Export failed: {e}"))

    # ---- MangoHud (frames) ---------------------------------------------------------------

    mangohud = Property(str, lambda self: self._mh, notify=stateChanged)
    mangohudConf = Property(str, lambda self: sessions.MANGOHUD_CONF, constant=True)
    mangohudLines = Property("QVariantList", lambda self: sessions.MANGOHUD_LINES, constant=True)

    @Slot()
    def setupMangohud(self):
        try:
            path = sessions.setup_mangohud()
            self.toast.emit(f"MangoHud set up ({path})")
        except (OSError, RuntimeError) as e:
            self.toast.emit(str(e))
        self._mh = sessions.mangohud_state()
        self.stateChanged.emit()
