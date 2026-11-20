"""Словарь: слово, транскрипция, перевод, пример, подуровень, статус."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit

from grasp.core.content import load_vocabulary
from grasp.core.levels import SUBLEVEL_CODES
from grasp.ui.context import AppContext
from grasp.ui.widgets.common import Label, Page
from grasp.ui.widgets.tables import AutoHeightTable

COLUMNS = ("Слово", "Транскрипция", "Перевод", "Пример", "Уровень", "Статус")


class DictionaryPage(Page):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__("Словарь", "Слова с транскрипцией, примерами и подуровнем. Озвучка — в версии 0.3.", max_chars=None)
        self.words = load_vocabulary()
        filters = QHBoxLayout()
        filters.setSpacing(12)
        self.search = QLineEdit()
        self.search.setObjectName("DictionarySearch")
        self.search.setPlaceholderText("Поиск по слову или переводу…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh)
        filters.addWidget(self.search, 1)
        self.level = QComboBox()
        self.level.addItem("Все уровни", "")
        for code in SUBLEVEL_CODES:
            self.level.addItem(code, code)
        self.level.currentIndexChanged.connect(self._refresh)
        filters.addWidget(self.level)
        self.body.addLayout(filters)

        self.count = Label("", "caption")
        self.add(self.count)
        self.table = AutoHeightTable(0, len(COLUMNS), min_col_chars=14)
        self.table.setObjectName("DictionaryTable")
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.add(self.table)
        self._refresh()
        self.finish()

    def _refresh(self) -> None:
        q = self.search.text().strip().lower()
        lvl = self.level.currentData()
        rows = [
            w
            for w in self.words
            if (not lvl or w["level"] == lvl)
            and (not q or q in w["word"].lower() or q in w["translation_ru"].lower())
        ]
        self.table.setRowCount(len(rows))
        for r, w in enumerate(rows):
            for c, value in enumerate(
                (w["word"], w["ipa"], w["translation_ru"], w["example"], w["level"], "новое")
            ):
                self.table.set_cell(r, c, value)
        self.count.setText(f"Показано слов: {len(rows)} из {len(self.words)}")
        self.table._fit()
