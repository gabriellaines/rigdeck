"""`settingsFile` in QML: import / export every device's settings as one JSON file."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from .. import setupfile
from .bridge import run_async

# backends whose pages show settings an import may change, and how to make them re-read
REFRESH = (("cooler", "reload"), ("cooler", "reloadLed"), ("motherboard", "refreshLighting"),
           ("keyboard", "lightingChangedElsewhere"), ("keyboard", "refresh"), ("mouse", "refresh"),
           ("headset", "refresh"), ("lighting", "refresh"))


def _path(url: str) -> str:
    return QUrl(url).toLocalFile() or url


class SettingsFile(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, ctx):
        super().__init__()
        self._ctx = ctx
        self._busy = ""
        self._results: list = []      # [{title, ok, message}] of the last import, or its problems
        self._file = ""

    busy = Property(str, lambda self: self._busy, notify=changed)
    results = Property("QVariantList", lambda self: self._results, notify=changed)
    file = Property(str, lambda self: self._file, notify=changed)

    def _set(self, busy="", results=None, file=None):
        self._busy = busy
        if results is not None:
            self._results = results
        if file is not None:
            self._file = file
        self.changed.emit()

    @Slot(str)
    def importFile(self, url):
        if self._busy:
            return
        path = _path(url)
        name = path.rsplit("/", 1)[-1]
        self._set("Setting up your devices…", [], name)

        def work():
            with open(path) as f:
                data = setupfile.parse(f.read())
            return setupfile.apply(data)

        def done(results):
            self._set("", results)
            ok = sum(r["ok"] for r in results)
            self.toast.emit(f"{name}: all {ok} set" if ok == len(results)
                            else f"{name}: {ok} of {len(results)} set — see Settings")
            self._refresh_pages()

        def failed(e):
            problems = e.problems if isinstance(e, setupfile.FileError) else [getattr(e, "strerror", None) or str(e)]
            self._set("", [{"title": "Not used — nothing was changed", "ok": False, "message": p} for p in problems])
            self.toast.emit(f"{name} wasn't used: {problems[0]}")
        run_async(work, done, failed)

    @Slot(str)
    def exportFile(self, url):
        if self._busy:
            return
        path = _path(url)
        if not path.endswith(".json"):
            path += ".json"
        self._set("Reading your devices…")

        def work():
            data = setupfile.export()
            with open(path, "w") as f:
                f.write(setupfile.dumps(data))
            return [setupfile.SECTIONS[k][0] for k in data if k in setupfile.SECTIONS]

        def done(sections):
            self._set("")
            self.toast.emit(f"Saved {', '.join(sections) or 'nothing'} to {path.rsplit('/', 1)[-1]}")

        def failed(e):
            self._set("")
            self.toast.emit(f"Could not save the file: {getattr(e, 'strerror', None) or e}")
        run_async(work, done, failed)

    def _refresh_pages(self):
        for page_id, method in REFRESH:
            backend = self._ctx.contextProperty(page_id)
            if backend is not None and hasattr(backend, method):
                getattr(backend, method)()
