"""`image://icons/<name>/<rrggbb>` — Lucide SVG icons recolored for the current theme."""
from __future__ import annotations

import os
from functools import lru_cache

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = os.path.join(os.path.dirname(__file__), "icons")


@lru_cache(maxsize=None)
def _svg(name: str) -> bytes | None:
    path = os.path.join(ICON_DIR, os.path.basename(name) + ".svg")
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


class IconProvider(QQuickImageProvider):
    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, icon_id: str, size: QSize, requested: QSize) -> QImage:
        name, _, color = icon_id.partition("/")
        color = "#" + (color or "000000")
        side = max(requested.width(), requested.height(), 16)
        img = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        data = _svg(name) or _svg("box")
        if data:
            r = QSvgRenderer(QByteArray(data.replace(b"currentColor", color.encode())))
            p = QPainter(img)
            r.render(p)
            p.end()
        if size is not None:
            size.setWidth(side)
            size.setHeight(side)
        return img
