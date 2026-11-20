"""Сборка app.ico из app.svg: 16…256 px, каждый размер отрисован отдельно
(а не уменьшен из 256), чтобы иконка была чёткой и на 100 %, и на 4K.

    python tools/make_icon.py
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "grasp" / "resources" / "icons"
SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)


def render(renderer: QSvgRenderer, size: int) -> Image.Image:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> int:
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    svg = (ICONS / "app.svg").read_bytes()
    renderer = QSvgRenderer(QByteArray(svg))
    images = [render(renderer, s) for s in SIZES]
    big = images[-1]
    out = ICONS / "app.ico"
    big.save(out, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    big.save(ICONS / "app-256.png")
    with Image.open(out) as ico:
        print(f"{out.relative_to(ROOT)}: {sorted(ico.info.get('sizes', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
