"""SVG-иконки, перекрашиваемые под тему.

Иконки рисуются через QSvgRenderer в нужном размере и с учётом
devicePixelRatio, поэтому остаются чёткими на 4K и при 250 %.
``currentColor`` в SVG заменяется цветом токена темы.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from grasp.paths import resource_path


@lru_cache(maxsize=None)
def _svg_source(name: str) -> str:
    return resource_path("resources", "icons", f"{name}.svg").read_text(encoding="utf-8")


class SvgIconEngine(QIconEngine):
    def __init__(self, name: str, color: str) -> None:
        super().__init__()
        self._name = name
        self._color = color
        data = _svg_source(name).replace("currentColor", color)
        self._renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))

    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        if mode == QIcon.Mode.Disabled:
            painter.setOpacity(0.45)
        self._renderer.render(painter, QRectF(rect))

    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    def scaledPixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float) -> QPixmap:
        pm = QPixmap(size * scale)
        pm.setDevicePixelRatio(scale)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pm

    def clone(self) -> "SvgIconEngine":
        return SvgIconEngine(self._name, self._color)


def icon(name: str, color: str) -> QIcon:
    return QIcon(SvgIconEngine(name, color))


def app_icon() -> QIcon:
    """Иконка окна: .ico (Windows, все размеры) или SVG как запасной вариант."""
    ico = resource_path("resources", "icons", "app.ico")
    if ico.exists():
        return QIcon(str(ico))
    return QIcon(str(resource_path("resources", "icons", "app.svg")))
