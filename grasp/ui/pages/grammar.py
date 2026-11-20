"""Грамматика: «По темам» и «По уровням» — один контент, общий прогресс."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from grasp.core.content import Topic, load_topics, read_json, rules_by_level
from grasp.core.levels import SUBLEVEL_CODES, load_sublevels
from grasp.ui.context import AppContext
from grasp.ui.pages import coming_soon
from grasp.ui.widgets.common import Card, Label, Page, SegmentedControl, chip
from grasp.ui.widgets.flow_layout import flow_container
from grasp.ui.widgets.tables import AutoHeightTable


def tenses_table() -> AutoHeightTable:
    data = read_json("grammar", "tenses_overview.json")
    aspects, times = data["aspects"], data["times"]
    table = AutoHeightTable(len(aspects), len(times), min_col_chars=19)
    table.setObjectName("TensesTable")
    table.setHorizontalHeaderLabels(times)
    table.setVerticalHeaderLabels(aspects)
    for cell in data["cells"]:
        r, c = aspects.index(cell["aspect"]), times.index(cell["time"])
        table.set_cell(r, c, f"{cell['name']}  ·  {cell['level']}\n{cell['form']}\n{cell['example']}")
    return table


class RuleRow(QWidget):
    def __init__(self, level: str, title: str, extra: str = "") -> None:
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(12)
        row.addWidget(chip(level, "tag"), 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(Label(title))
        if extra:
            text.addWidget(Label(extra, "caption"))
        row.addLayout(text, 1)


class TopicCard(Card):
    def __init__(self, topic: Topic, expanded: bool = False) -> None:
        super().__init__()
        self.setObjectName(f"Topic-{topic.id}")
        lo, hi = topic.level_range
        head = QHBoxLayout()
        head.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(Label(topic.title_ru, "h3"))
        titles.addWidget(Label(topic.title_en, "caption"))
        head.addLayout(titles, 1)
        head.addWidget(chip(f"{lo} → {hi}", "tag"), 0, Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(head)
        self.add(Label(topic.summary_ru, "secondary"))

        self.details = QWidget()
        dv = QVBoxLayout(self.details)
        dv.setContentsMargins(0, 4, 0, 0)
        dv.setSpacing(6)
        if topic.id == "tenses":
            dv.addWidget(Label("Обзор: 4 аспекта × 3 времени", "h3"))
            dv.addWidget(tenses_table())
        for rule in topic.rules:
            dv.addWidget(RuleRow(rule.level, rule.title))
        self.details.setVisible(expanded)
        self.add(self.details)

        btns = QHBoxLayout()
        self.toggle = QPushButton()
        self.toggle.clicked.connect(self._toggle)
        start = QPushButton("Изучить тему целиком")
        start.setProperty("role", "primary")
        start.clicked.connect(lambda: coming_soon(self, f"Модуль «{topic.title_ru}»", "0.4"))
        btns.addWidget(start)
        btns.addWidget(self.toggle)
        btns.addStretch(1)
        self.body.addLayout(btns)
        self._count = len(topic.rules)
        self._sync()

    def _toggle(self) -> None:
        self.details.setVisible(not self.details.isVisible())
        self._sync()

    def _sync(self) -> None:
        shown = self.details.isVisibleTo(self)
        self.toggle.setText("Свернуть" if shown else f"Правила темы ({self._count})")


class GrammarPage(Page):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__(
            "Грамматика",
            "Каждое правило — коротко на русском, с примерами, исключениями и типичными ошибками. "
            "Правило, пройденное в теме, засчитывается и в маршруте по уровням.",
        )
        self.ctx = ctx
        self.switch = SegmentedControl([("topics", "По темам"), ("levels", "По уровням")], ctx.settings.grammar_view)
        self.switch.setObjectName("GrammarSwitch")
        self.switch.changed.connect(self._set_view)
        self.add(self.switch)

        # Два вида в одном layout; неактивный скрыт (QStackedWidget взял бы
        # высоту по самому длинному виду и оставил пустое место).
        self.views = {"topics": self._topics_view(), "levels": self._levels_view()}
        for key, view in self.views.items():
            view.setObjectName(f"GrammarView-{key}")
            self.add(view)
        self._set_view(ctx.settings.grammar_view, save=False)

        tip = Card("Подсказка")
        tip.add(Label("«По темам» — чтобы закрыть тему целиком. «По уровням» — чтобы идти по маршруту A1.1 → C2.2.", "secondary"))
        self.add_side(tip)
        self.finish()

    def _topics_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(16)
        for i, topic in enumerate(load_topics()):
            v.addWidget(TopicCard(topic, expanded=(i == 0)))
        return w

    def _levels_view(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(16)
        topics = {t.id: t for t in load_topics()}
        infos = load_sublevels()
        grouped = rules_by_level()
        for code in SUBLEVEL_CODES:
            card = Card()
            card.setObjectName(f"Level-{code}")
            head = QHBoxLayout()
            head.addWidget(chip(code, "current"), 0, Qt.AlignmentFlag.AlignTop)
            head.addWidget(Label(infos[code].title_ru, "h3"), 1)
            card.body.addLayout(head)
            card.add(Label(infos[code].summary_ru, "secondary"))
            for rule in grouped[code]:
                card.add(RuleRow(code, rule.title, topics[rule.topic_id].title_ru))
            box, flow = flow_container(6)
            for theme in infos[code].vocab_themes:
                flow.addWidget(chip(theme, "tag"))
            card.add(Label(f"Словарь к концу ступени ≈ {infos[code].vocab_target} слов. Темы:", "caption"))
            card.add(box)
            v.addWidget(card)
        return w

    def _set_view(self, key: str, save: bool = True) -> None:
        for name, view in self.views.items():
            view.setVisible(name == key)
        self.switch.set_current(key)
        if save:
            self.ctx.settings.grammar_view = key
            self.ctx.save()
