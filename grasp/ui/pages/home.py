"""Главная: подуровень, шкала 12 ступеней, навыки, TOEFL, повторение."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from grasp.core.levels import SKILL_NAMES_RU, SUBLEVEL_CODES, Level, expected_toefl, load_sublevels
from grasp.data.db import get_profile
from grasp.ui.context import AppContext
from grasp.ui.pages import coming_soon
from grasp.ui.widgets.common import Card, Label, Page, chip, progress_row, tone_label
from grasp.ui.widgets.flow_layout import flow_container


def _fmt_score(score: float) -> str:
    return f"{score:.1f}".replace(".", ",")


class HomePage(Page):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__("Главная", "Ваш маршрут от A1.1 до C2.2 и подготовка к TOEFL iBT.", max_chars=84)
        self.ctx = ctx
        profile = get_profile(ctx.db)
        levels = load_sublevels()
        lvl = Level(profile.current_level)
        info = levels[lvl.code]
        nxt = lvl.next()

        # --- текущий подуровень ------------------------------------------
        hero = Card()
        top = QHBoxLayout()
        top.setSpacing(24)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(4)
        lv.addWidget(Label("Текущий подуровень", "secondary"))
        code = Label(lvl.code, "display", wrap=False)
        code.setObjectName("CurrentLevel")
        lv.addWidget(code)
        lv.addWidget(Label(info.title_ru, "h3"))
        top.addWidget(left, 0, Qt.AlignmentFlag.AlignTop)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(8)
        score = expected_toefl(lvl.code, profile.level_progress)
        rv.addWidget(Label("Ожидаемый балл TOEFL iBT", "secondary"))
        score_lbl = Label(f"{_fmt_score(score)} из 6", "h2")
        score_lbl.setObjectName("ToeflScore")
        rv.addWidget(score_lbl)
        rv.addWidget(Label(f"Шкала 1–6: {lvl.cefr} ≈ {lvl.toefl_band}. Цель: {_fmt_score(ctx.settings.target_toefl)}.", "caption"))
        top.addWidget(right, 1, Qt.AlignmentFlag.AlignTop)
        hero.body.addLayout(top)
        hero.add(Label(info.summary_ru, "secondary"))
        if nxt:
            hero.add(progress_row(f"Прогресс до {nxt.code}", profile.level_progress))
            hero.add(
                Label(
                    "Переход на следующую ступень — после итогового теста подуровня на 80 % и выше. "
                    "Тест можно сдать досрочно и перескочить подуровень.",
                    "caption",
                )
            )
        if not profile.placement_done:
            hero.add(
                tone_label(
                    "Вы ещё не проходили вводный тест. Он займёт 20–30 минут и определит подуровень "
                    "отдельно по грамматике, лексике, чтению и аудированию.",
                    "info",
                )
            )
            btns = QHBoxLayout()
            start = QPushButton("Пройти вводный тест")
            start.setProperty("role", "primary")
            start.clicked.connect(lambda: coming_soon(self, "Вводный тест", "0.6"))
            btns.addWidget(start)
            btns.addStretch(1)
            hero.body.addLayout(btns)
        self.add(hero)

        # --- шкала 12 ступеней -------------------------------------------
        ladder = Card("Путь A1.1 → C2.2")
        box, flow = flow_container(8)
        for c in SUBLEVEL_CODES:
            state = "done" if Level(c) < lvl else "current" if c == lvl.code else "future"
            ch = chip(c, state)
            ch.setToolTip(f"{c} — {levels[c].title_ru}. Словарь ≈ {levels[c].vocab_target} слов.")
            ch.setAccessibleName(f"{c}: {'пройден' if state == 'done' else 'текущий' if state == 'current' else 'впереди'}")
            flow.addWidget(ch)
        box.setObjectName("LevelLadder")
        ladder.add(box)
        ladder.add(Label("Зелёные — пройдены, синяя — текущая ступень, остальные — впереди.", "caption"))
        self.add(ladder)

        # --- навыки ------------------------------------------------------
        skills = Card("Навыки")
        by_skill = {s.skill: s for s in profile.skills}
        for key, name in SKILL_NAMES_RU.items():
            sp = by_skill.get(key)
            level = sp.level if sp else lvl.code
            progress = sp.progress if sp else 0.0
            skills.add(progress_row(f"{name} · {level}", progress))
        self.add(skills)

        # --- я умею (can-do) ---------------------------------------------
        cando = Card(f"На уровне {lvl.code} вы научитесь")
        for key, name in SKILL_NAMES_RU.items():
            for text in info.can_do.get(key, []):
                cando.add(Label(f"{name}: {text}"))
        self.add(cando)

        # --- боковая панель (на широких экранах) --------------------------
        today = Card("Сегодня")
        due = Label("На повторение: 0", "h2")
        due.setObjectName("DueToday")
        today.add(due)
        today.add(Label("Слова, правила и ваши ошибки из Журнала — по интервальному повторению.", "caption"))
        today.add(Label(f"Цель на день: {ctx.settings.minutes_per_day} мин", "secondary"))
        go = QPushButton("Открыть повторение")
        go.clicked.connect(lambda: ctx.navigate("review"))
        today.add(go)
        self.add_side(today)

        exam = Card("Экзамен")
        if ctx.settings.exam_date:
            try:
                days = (date.fromisoformat(ctx.settings.exam_date) - date.today()).days
                exam.add(Label(f"До TOEFL iBT: {max(days, 0)} дн.", "h3"))
            except ValueError:
                exam.add(Label("Дата экзамена не задана.", "secondary"))
        else:
            exam.add(Label("Укажите дату экзамена в настройках — Grasp рассчитает темп.", "secondary"))
        self.add_side(exam)

        philosophy = Card("Как учит Grasp")
        for line in (
            "Правила объясняются явно, на русском, с типичными ошибками.",
            "Тему можно пройти целиком — например, все 12 времён сразу.",
            "Вы пишете и говорите сами, а не угадываете варианты.",
            "Каждая ошибка возвращается к вам в повторении.",
        ):
            philosophy.add(Label(f"• {line}", "secondary"))
        self.add_side(philosophy)
        self.finish()
