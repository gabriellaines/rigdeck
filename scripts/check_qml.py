"""Compile every QML file in the package; print errors and exit 1 if any fails.

Context properties (theme, backends) aren't needed to compile, only to run, so this catches
syntax and type errors (e.g. redefining a built-in property) without starting the app.
Exits 2 if PySide6 isn't available, so callers can decide whether that's fatal.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
except ImportError:
    sys.exit(2)

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rigdeck")
app = QGuiApplication(sys.argv)
engine = QQmlEngine()
engine.addImportPath(os.path.join(root, "gui", "qml"))
failed = 0
files = sorted(os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f.endswith(".qml"))
for path in files:
    c = QQmlComponent(engine, QUrl.fromLocalFile(os.path.abspath(path)))
    if c.isError():
        failed += 1
        for e in c.errors():
            print(e.toString())
print(f"{len(files) - failed}/{len(files)} QML files compile")
sys.exit(1 if failed else 0)
