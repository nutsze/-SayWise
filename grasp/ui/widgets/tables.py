"""Таблицы, которые прокручиваются по горизонтали, а не сжимаются."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QSizePolicy, QTableWidget, QTableWidgetItem


class AutoHeightTable(QTableWidget):
    """Таблица без внутренней вертикальной прокрутки: высота = содержимое.

    * Колонки не уже ``min_col_chars`` символов → при нехватке ширины
      появляется горизонтальная полоса прокрутки, текст не обрезается.
    * Текст в ячейках переносится, высота строк пересчитывается под текст
      при каждом изменении ширины/шрифта.
    """

    def __init__(self, rows: int, cols: int, min_col_chars: int = 24, parent=None) -> None:
        super().__init__(rows, cols, parent)
        self.min_col_chars = min_col_chars
        self.setWordWrap(True)
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # Stretch-колонки получают ширину лениво; высоту строк пересчитываем
        # после каждого фактического изменения ширины колонки.
        self.horizontalHeader().sectionResized.connect(lambda *_: self._fit_rows())

    def set_cell(self, row: int, col: int, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setItem(row, col, item)
        return item

    def min_column_width(self) -> int:
        return self.fontMetrics().averageCharWidth() * self.min_col_chars

    def _fit(self) -> None:
        header = self.horizontalHeader()
        min_w = self.min_column_width()
        header.setMinimumSectionSize(min_w)
        vh = self.verticalHeader().width() if self.verticalHeader().isVisible() else 0
        total_min = min_w * self.columnCount() + vh + 2 * self.frameWidth()
        if self.viewport().width() + vh < total_min:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
            for c in range(self.columnCount()):
                header.resizeSection(c, min_w)
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._fit_rows()

    CELL_PAD_H = 12  # суммарный горизонтальный отступ текста в ячейке
    CELL_PAD_V = 12

    def row_height_for(self, row: int) -> int:
        """Высота строки под перенесённый текст во ВСЕХ колонках.

        Встроенный resizeRowsToContents() смотрит только на видимые колонки,
        и при горизонтальной прокрутке строки получались ниже текста.
        """
        fm = self.fontMetrics()
        best = fm.height()
        for c in range(self.columnCount()):
            item = self.item(row, c)
            if item is None or not item.text():
                continue
            width = max(1, self.columnWidth(c) - self.CELL_PAD_H)
            rect = fm.boundingRect(QRect(0, 0, width, 1_000_000), Qt.TextFlag.TextWordWrap, item.text())
            best = max(best, rect.height())
        vh = self.verticalHeader()
        if vh.isVisible():
            label = self.verticalHeaderItem(row)
            if label is not None:
                best = max(best, fm.height())
        return best + self.CELL_PAD_V

    def _fit_rows(self) -> None:
        header = self.horizontalHeader()
        for r in range(self.rowCount()):
            self.setRowHeight(r, self.row_height_for(r))
        h = header.height() + 2 * self.frameWidth()
        for r in range(self.rowCount()):
            h += self.rowHeight(r)
        if self.horizontalScrollBar().isVisible() or header.length() > self.viewport().width() + 1:
            h += self.horizontalScrollBar().sizeHint().height()
        self.setFixedHeight(h)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (event.Type.FontChange, event.Type.StyleChange):
            self._fit()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._fit()
