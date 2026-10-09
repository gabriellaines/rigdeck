"""`customThemes` in QML: import, save a template for, and remove a person's own theme files."""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from .. import customtheme
from .bridge import run_async


def _path(url: str) -> str:
    return QUrl(url).toLocalFile() or url


class CustomThemes(QObject):
    changed = Signal()
    toast = Signal(str)

    def __init__(self, theme):
        super().__init__()
        self._theme = theme
        self._busy = ""
        self._error = ""

    busy = Property(str, lambda self: self._busy, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)

    def _set(self, busy="", error=""):
        self._busy, self._error = busy, error
        self.changed.emit()

    @Slot(str)
    def importFile(self, url):
        if self._busy:
            return
        path = _path(url)
        name = path.rsplit("/", 1)[-1]
        self._set(f"Adding {name}…")

        def work():
            with open(path) as f:
                return customtheme.save(f.read())

        def done(result):
            slug, theme = result
            self._set()
            self._theme.reload_custom()
            self._theme.mode = f"custom:{slug}"
            self.toast.emit(f'Added theme "{theme["name"]}"')

        def failed(e):
            problems = e.problems if isinstance(e, customtheme.ThemeFileError) \
                else [getattr(e, "strerror", None) or str(e)]
            self._set(error=f"{name}: {problems[0]}")
            self.toast.emit(f"{name} wasn't added: {problems[0]}")
        run_async(work, done, failed)

    @Slot(str)
    def exportTemplate(self, url):
        if self._busy:
            return
        path = _path(url)
        if not path.endswith(".json"):
            path += ".json"
        self._set("Saving…")

        def work():
            text = customtheme.template(self._theme.tokens())
            with open(path, "w") as f:
                f.write(text)

        def done(_):
            self._set()
            self.toast.emit(f"Saved {path.rsplit('/', 1)[-1]} — edit its colors, then import it back")

        def failed(e):
            self._set()
            self.toast.emit(f"Could not save the file: {getattr(e, 'strerror', None) or e}")
        run_async(work, done, failed)

    @Slot(str)
    def remove(self, slug):
        customtheme.delete(slug)
        self._theme.reload_custom()
        self.toast.emit("Theme removed")
