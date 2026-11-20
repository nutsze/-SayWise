"""Базовые строительные блоки экранов."""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

ZWSP = "​"
_LONG_TOKEN = re.compile(r"\S{18,}")


def soft_wrap(text: str, chunk: int = 12) -> str:
    """Разрешить перенос внутри очень длинных «слов» (URL, пути, композиты).

    QLabel переносит только по пробелам, поэтому в длинные токены
    вставляются невидимые точки переноса (U+200B) после / . - _ и каждые
    ``chunk`` символов.
    """

    def fix(match: re.Match[str]) -> str:
        token = match.group(0)
        token = re.sub(r"([/\\._\-–—])", r"\1" + ZWSP, token)
        parts = token.split(ZWSP)
        out = []
        for part in parts:
            out.append(ZWSP.join(part[i : i + chunk] for i in range(0, len(part), chunk)))
        return ZWSP.join(out)

    return _LONG_TOKEN.sub(fix, text)


class Label(QLabel):
    """QLabel с переносом строк, ролью для QSS и защитой длинных слов."""

    def __init__(
        self,
        text: str = "",
        role: str | None = None,
        wrap: bool = True,
        selectable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWordWrap(wrap)
        if role:
            self.setProperty("role", role)
        if selectable:
            self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        if wrap:
            sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            sp.setHeightForWidth(True)
            self.setSizePolicy(sp)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(soft_wrap(text) if self.wordWrap() and self.textFormat() != Qt.TextFormat.RichText else text)


def tone_label(text: str, tone: str) -> Label:
    lbl = Label(text)
    lbl.setProperty("tone", tone)
    return lbl


def chip(text: str, state: str = "tag") -> QLabel:
    lbl = QLabel(text)
    lbl.setProperty("chip", "true")
    lbl.setProperty("state", state)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl


class Card(QFrame):
    """Карточка-поверхность с вертикальным layout."""

    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", "true")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(10)
        if title:
            self.body.addWidget(Label(title, "h3"))
        sp = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        sp.setHeightForWidth(True)
        self.setSizePolicy(sp)

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget


def progress_row(caption: str, value: float, tone: str | None = None) -> QWidget:
    """«Подпись ........ 45 %» + полоска прогресса."""
    w = QWidget()
    v = QVBoxLayout(w)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)
    head = QHBoxLayout()
    head.setSpacing(8)
    head.addWidget(Label(caption), 1)
    pct = QLabel(f"{round(value * 100)} %")
    pct.setProperty("role", "secondary")
    head.addWidget(pct, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
    v.addLayout(head)
    bar = QProgressBar()
    bar.setRange(0, 1000)
    bar.setValue(int(value * 1000))
    bar.setTextVisible(False)
    if tone:
        bar.setProperty("tone", tone)
    bar.setAccessibleName(f"{caption}: {round(value * 100)} %")
    v.addWidget(bar)
    return w


class SegmentedControl(QWidget):
    """Переключатель из нескольких кнопок (например, «По темам / По уровням»)."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], current: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, title in options:
            btn = QPushButton(title)
            btn.setCheckable(True)
            btn.setProperty("segment", "true")
            btn.setChecked(key == current)
            btn.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
            self.group.addButton(btn)
            layout.addWidget(btn)
            self.buttons[key] = btn
        layout.addStretch(1)

    def set_current(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)


class Page(QWidget):
    """Экран: прокрутка + ограниченная по ширине колонка + боковая панель.

    * Колонка текста не шире ``max_chars`` символов текущего шрифта
      (≈ 70–80 знаков в строке — удобное чтение и на 4K).
    * Боковая панель (``side``) появляется, только если рядом с колонкой
      хватает места — то есть на больших экранах.
    """

    SIDE_WIDTH_CHARS = 34

    def __init__(self, title: str, subtitle: str = "", max_chars: int | None = 78, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.max_chars = max_chars
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("PageContent")
        self.scroll.setWidget(content)
        row = QHBoxLayout(content)
        row.setContentsMargins(32, 28, 32, 32)
        row.setSpacing(28)
        row.addStretch(1)

        self.column = QWidget()
        self.column.setObjectName("Column")
        col_sp = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.column.setSizePolicy(col_sp)
        self.body = QVBoxLayout(self.column)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(16)
        row.addWidget(self.column, 100)

        self.side = QFrame()
        self.side.setObjectName("SidePanel")
        self.side_body = QVBoxLayout(self.side)
        self.side_body.setContentsMargins(0, 0, 0, 0)
        self.side_body.setSpacing(16)
        self.side.setVisible(False)
        # Без AlignTop: с выравниванием layout отдаёт панели sizeHint, а не
        # heightForWidth, и перенесённый текст обрезается. Кверху прижимает
        # stretch в конце side_body.
        row.addWidget(self.side)
        row.addStretch(1)
        self._row = row

        self.title_label = Label(title, "title")
        self.title_label.setAccessibleName(title)
        self.body.addWidget(self.title_label)
        if subtitle:
            self.body.addWidget(Label(subtitle, "secondary"))

    # -- API для экранов ---------------------------------------------------
    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget

    def add_side(self, widget: QWidget) -> QWidget:
        self.side_body.addWidget(widget)
        return widget

    def finish(self) -> None:
        """Вызвать после добавления виджетов: прижать содержимое кверху."""
        self.body.addStretch(1)
        self.side_body.addStretch(1)
        self.relayout()

    # -- адаптивность ------------------------------------------------------
    def _char_width(self) -> int:
        return max(6, self.fontMetrics().averageCharWidth())

    def relayout(self) -> None:
        cw = self._char_width()
        avail = self.scroll.viewport().width() - 64
        side_w = cw * self.SIDE_WIDTH_CHARS
        col_max = cw * self.max_chars if self.max_chars else 10**6
        has_side = self.side_body.count() > 0
        show_side = has_side and avail >= min(col_max, cw * 70) + side_w + 28
        self.side.setVisible(show_side)
        self.side.setFixedWidth(side_w)
        self.column.setMaximumWidth(col_max if self.max_chars else 16777215)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.relayout()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (event.Type.FontChange, event.Type.StyleChange):
            self.relayout()


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setProperty("role", "divider")
    return line
