"""Встроенные шрифты: Noto Sans и Noto Sans Mono (лицензия OFL).

Не полагаемся на системные шрифты: на чистой Windows может не оказаться
глифов IPA (ə, ʃ, ʒ, θ, ð, ŋ, ˈ, ː).
"""

from __future__ import annotations

import logging

from PySide6.QtGui import QFontDatabase

from grasp.paths import resource_path

log = logging.getLogger(__name__)

SANS = "Noto Sans"
MONO = "Noto Sans Mono"
# Запасные семейства для символов, которых нет в Noto Sans (→ ≈ ✓ ✗).
# Порядок важен: Qt ищет глиф по списку слева направо.
SANS_STACK = (SANS, "Noto Sans Math", "Noto Sans Symbols 2")
FONT_FILES = (
    "NotoSans-Regular.ttf",
    "NotoSans-Italic.ttf",
    "NotoSans-SemiBold.ttf",
    "NotoSans-Bold.ttf",
    "NotoSans-BoldItalic.ttf",
    "NotoSansMono-Regular.ttf",
    "NotoSansMono-Bold.ttf",
    "NotoSansMath-Regular.ttf",
    "NotoSansSymbols2-Regular.ttf",
)

_loaded: set[str] = set()


def load_fonts() -> set[str]:
    """Зарегистрировать шрифты в Qt. Возвращает загруженные семейства."""
    for name in FONT_FILES:
        path = resource_path("resources", "fonts", name)
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            log.error("Не удалось загрузить шрифт %s", path)
            continue
        _loaded.update(QFontDatabase.applicationFontFamilies(font_id))
    missing = {MONO, *SANS_STACK} - _loaded
    if missing:
        log.error("Не загружены семейства шрифтов: %s", missing)
    return set(_loaded)


def qss_family(stack: tuple[str, ...] = SANS_STACK) -> str:
    return ", ".join(f'"{name}"' for name in stack)
