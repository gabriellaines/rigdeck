"""`rigdeck-gui`: the Qt 6 / QML app."""
from __future__ import annotations

import sys

MISSING_DEPS = """rigdeck-gui needs Qt 6 for Python (PySide6). Install it with:
  Arch/CachyOS/Manjaro:  sudo pacman -S pyside6 qt6-svg
  Fedora:                sudo dnf install python3-pyside6
  Debian/Ubuntu:         sudo apt install python3-pyside6.qtquick python3-pyside6.qtquickcontrols2 \\
                             python3-pyside6.qtsvg qml6-module-qtquick-controls qml6-module-qtquick-layouts \\
                             qml6-module-qtquick-dialogs qml6-module-qtquick-effects
  openSUSE:              sudo zypper install python3-PySide6
The command-line tool `rigdeck` works without it."""


def main():
    try:
        import PySide6.QtQuick  # noqa: F401
        import PySide6.QtSvg  # noqa: F401
    except ImportError:
        sys.exit(MISSING_DEPS)
    from .app import run
    sys.exit(run(list(sys.argv)))
