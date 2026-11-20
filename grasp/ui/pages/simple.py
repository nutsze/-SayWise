"""Экраны, которые в 0.1 показывают структуру и пустые состояния:
Повторение, Журнал ошибок, TOEFL."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout

from grasp.core.content import read_json
from grasp.ui.context import AppContext
from grasp.ui.pages import coming_soon
from grasp.ui.widgets.common import Card, Label, Page, chip, tone_label


class ReviewPage(Page):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__("Повторение", "Слова, правила и ваши ошибки — в одной очереди интервального повторения.")
        summary = Card("Сегодня")
        due = Label("На повторение: 0", "h2")
        due.setObjectName("ReviewDue")
        summary.add(due)
        summary.add(
            tone_label(
                "Очередь пуста. Карточки появятся, когда вы начнёте проходить уроки: "
                "каждое новое слово, правило и каждая ошибка попадают сюда.",
                "info",
            )
        )
        self.add(summary)

        how = Card("Как это работает")
        for line in (
            "Алгоритм FSRS подбирает момент повторения — прямо перед тем, как вы забыли бы материал.",
            "Вы отвечаете сами (пишете или говорите), а затем оцениваете, насколько легко вспомнили.",
            "Ошибки из Журнала превращаются в новые задания на то же правило.",
        ):
            how.add(Label(f"• {line}", "secondary"))
        self.add(how)
        start = QPushButton("Начать повторение")
        start.setProperty("role", "primary")
        start.clicked.connect(lambda: coming_soon(self, "Интервальное повторение", "0.5"))
        row = QHBoxLayout()
        row.addWidget(start)
        row.addStretch(1)
        self.body.addLayout(row)
        self.finish()


class MistakesPage(Page):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__("Журнал ошибок", "Каждая ошибка сохраняется с правилом, к которому она относится.")
        empty = Card()
        empty.setObjectName("MistakesEmpty")
        empty.add(Label("Пока ошибок нет", "h2"))
        empty.add(
            Label(
                "Ошибки будут сгруппированы по типу — например, «Present Perfect vs Past Simple» "
                "или «артикли с исчисляемыми». У каждой группы — кнопка «Потренировать».",
                "secondary",
            )
        )
        self.add(empty)
        typical = Card("Типичные ошибки русскоговорящих, которые Grasp отслеживает")
        for line in (
            "Пропуск артикля: «I have cat» вместо «I have a cat».",
            "Present Simple вместо Present Perfect: «I know him for years».",
            "Порядок слов в косвенном вопросе: «Tell me where is the station».",
            "Лишний предлог: «discuss about», «enter into the room».",
        ):
            typical.add(Label(f"• {line}", "secondary"))
        self.add(typical)
        self.finish()


class ToeflPage(Page):
    def __init__(self, ctx: AppContext) -> None:
        data = read_json("toefl", "sections.json")
        super().__init__("TOEFL iBT", f"{data['format']}. {data['score_scale']}.", max_chars=90)
        self.add(tone_label(data["note"], "info"))
        for section in data["sections"]:
            card = Card()
            card.setObjectName(f"Toefl-{section['id']}")
            card.add(Label(section["title_ru"], "h2"))
            for task in section["tasks"]:
                row = QHBoxLayout()
                row.setSpacing(12)
                col = QVBoxLayout()
                col.setSpacing(2)
                col.addWidget(Label(task["title"], "h3"))
                col.addWidget(Label(task["description_ru"], "secondary"))
                row.addLayout(col, 1)
                btn = QPushButton("Тренировать")
                btn.clicked.connect(lambda _=False, t=task["title"]: coming_soon(self, f"Задание «{t}»", "0.7"))
                row.addWidget(btn, 0, Qt.AlignmentFlag.AlignTop)
                card.body.addLayout(row)
            self.add(card)

        mock = Card("Пробный тест")
        mock.add(Label("Полный тест с таймером по секциям и итоговым баллом 1–6.", "secondary"))
        b = QPushButton("Начать пробный тест")
        b.setProperty("role", "primary")
        b.clicked.connect(lambda: coming_soon(self, "Пробный тест TOEFL", "0.7"))
        row = QHBoxLayout()
        row.addWidget(b)
        row.addStretch(1)
        mock.body.addLayout(row)
        self.add_side(mock)

        history = Card("История баллов")
        history.add(Label("Здесь появятся результаты ваших пробных тестов и заданий.", "secondary"))
        scale = QHBoxLayout()
        for band in range(1, 7):
            scale.addWidget(chip(str(band), "future"))
        scale.addStretch(1)
        history.body.addLayout(scale)
        history.add(Label("1 ≈ A1 · 2 ≈ A2 · 3 ≈ B1 · 4 ≈ B2 · 5 ≈ C1 · 6 ≈ C2", "caption"))
        self.add_side(history)
        self.finish()
