"""Game monitor: record CPU, memory, GPU and disk telemetry while playing, then review it.

The recording itself lives in rigdeck/sessions.py and runs as its own process, so closing or
minimising RigDeck doesn't stop it.
"""
from __future__ import annotations

import os
import time

from ... import sessions
from ..base import Module, RigdeckError


def _dur(sec) -> str:
    sec = int(sec or 0)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def cli_record(a):
    sid = sessions.run(a.name or "")
    print(f"session {sid} saved")


def cli_start(a):
    if sessions.recording():
        raise RigdeckError("already recording — `rigdeck session stop` first")
    sessions.start_background(a.name or "")
    st = sessions.recording()
    if not st:
        raise RigdeckError("the recorder didn't start")
    print(f"recording session {st['id']} — stop with `rigdeck session stop`")


def cli_stop(a):
    sid = sessions.stop()
    print(f"session {sid} saved" if sid else "nothing is being recorded")


def cli_status(a):
    st = sessions.recording()
    if not st:
        print("not recording")
        return
    n = len(sessions.load_samples(st["id"]))
    print(f"recording {st['id']} since {st['started']} ({_dur(n * sessions.INTERVAL)}, {n} samples)")


def cli_list(a):
    rows = sessions.list_sessions()
    if not rows:
        print("no sessions yet — `rigdeck session start`")
    for s in rows:
        state = "" if s["finished"] else "  (recording)" if (sessions.recording() or {}).get("id") == s["id"] else "  (unfinished)"
        print(f"{s['id']}  {_dur(s['duration']):>8}  {s['game'] or '—':<24}{s['name']}{state}")


def cli_show(a):
    d = sessions.details(a.id)
    if not d["samples"]:
        raise RigdeckError(f"no session {a.id}")
    sm = d["summary"]
    print(f"Session {a.id}  ({_dur(sm['duration'])}, game: {sm.get('game') or 'unknown'})")
    print(f"{'':<26}{'avg':>8}{'p95':>8}{'max':>8}")
    for key, (label, unit) in sessions.METRICS.items():
        st = sm["metrics"].get(key)
        if st:
            print(f"{label + ' (' + unit + ')':<26}{st['avg']:>8g}{st['p95']:>8g}{st['max']:>8g}")
    for disk, ds in sm["disks"].items():
        t = f", max {ds['temp']['max']:g} °C" if ds.get("temp") else ""
        print(f"{disk}: read {ds['read'] / 1e9:.2f} GB, written {ds['written'] / 1e9:.2f} GB{t}")


def cli_export(a):
    print(sessions.export_csv(a.id, a.file))


def cli_delete(a):
    sessions.delete(a.id)
    print(f"deleted {a.id}")


class GameMonitorModule(Module):
    id = "gamemon"
    title = "Game monitor"
    icon = "gamepad-2"
    kind = "system"
    order = 6

    def detect(self) -> bool:
        return True

    def add_cli(self, sub):
        p = sub.add_parser("session", help="game monitor: record CPU / GPU / memory / disk while you play")
        ss = p.add_subparsers(dest="session_cmd", required=True)
        for name, fn, help_ in (("start", cli_start, "start recording in the background"),
                                ("record", cli_record, "record in the foreground until Ctrl+C")):
            x = ss.add_parser(name, help=help_)
            x.add_argument("--name", help="a label, e.g. the game or the settings you're testing")
            x.set_defaults(func=fn)
        ss.add_parser("stop", help="stop and save the recording").set_defaults(func=cli_stop)
        ss.add_parser("status", help="is something being recorded?").set_defaults(func=cli_status)
        ss.add_parser("list", help="recorded sessions").set_defaults(func=cli_list)
        for name, fn, help_ in (("show", cli_show, "summary of a session"), ("delete", cli_delete, "delete a session")):
            x = ss.add_parser(name, help=help_)
            x.add_argument("id")
            x.set_defaults(func=fn)
        e = ss.add_parser("export", help="write a session as CSV")
        e.add_argument("id")
        e.add_argument("file")
        e.set_defaults(func=cli_export)

    def qml_page(self):
        return os.path.join(os.path.dirname(__file__), "qml", "GameMonitorPage.qml")

    def qt_backend(self, app):
        from .qt import GameMonitorBackend
        return GameMonitorBackend()
