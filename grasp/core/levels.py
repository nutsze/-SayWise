"""Модель уровней: 6 уровней CEFR × 2 подуровня = 12 ступеней.

Коды ступеней фиксированы в коде (на них ссылается весь контент через поле
``level``), а описания — словарь, can-do, связь с TOEFL — в
``content/levels.json``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache, total_ordering

from grasp.paths import content_path

CEFR = ("A1", "A2", "B1", "B2", "C1", "C2")
SUBLEVEL_CODES: tuple[str, ...] = tuple(f"{c}.{n}" for c in CEFR for n in (1, 2))
SKILLS = ("reading", "listening", "writing", "speaking")
SKILL_NAMES_RU = {
    "reading": "Чтение",
    "listening": "Аудирование",
    "writing": "Письмо",
    "speaking": "Говорение",
}
PASS_THRESHOLD = 0.80  # итоговый тест подуровня: 80%+
TOEFL_BAND = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}

_CODE_RE = re.compile(r"^(A1|A2|B1|B2|C1|C2)\.(1|2)$")


def is_valid_level(code: str) -> bool:
    return bool(_CODE_RE.match(code or ""))


@total_ordering
@dataclass(frozen=True)
class Level:
    """Сравнимый код ступени: ``Level("B1.2") < Level("B2.1")``."""

    code: str

    def __post_init__(self) -> None:
        if not is_valid_level(self.code):
            raise ValueError(f"Неизвестный подуровень: {self.code!r}")

    @property
    def index(self) -> int:
        return SUBLEVEL_CODES.index(self.code)

    @property
    def cefr(self) -> str:
        return self.code.split(".")[0]

    @property
    def toefl_band(self) -> int:
        return TOEFL_BAND[self.cefr]

    def next(self) -> "Level | None":
        i = self.index + 1
        return Level(SUBLEVEL_CODES[i]) if i < len(SUBLEVEL_CODES) else None

    def prev(self) -> "Level | None":
        i = self.index - 1
        return Level(SUBLEVEL_CODES[i]) if i >= 0 else None

    def __lt__(self, other: "Level") -> bool:
        return self.index < other.index

    def __str__(self) -> str:
        return self.code


def expected_toefl(code: str, progress: float = 0.0) -> float:
    """Ожидаемый балл TOEFL (шкала 1–6, шаг 0.5).

    Первая половина CEFR-уровня (x.1) даёт целый балл, вторая (x.2) —
    +0.5 при прогрессе ступени от 50%. Это ориентир, а не прогноз ETS.
    """
    lvl = Level(code)
    score = float(lvl.toefl_band)
    if lvl.code.endswith(".2") and progress >= 0.5 and score < 6:
        score += 0.5
    return score


@dataclass
class SublevelInfo:
    code: str
    title_ru: str
    summary_ru: str
    vocab_target: int
    can_do: dict[str, list[str]] = field(default_factory=dict)
    vocab_themes: list[str] = field(default_factory=list)

    @property
    def level(self) -> Level:
        return Level(self.code)


@lru_cache(maxsize=1)
def load_sublevels() -> dict[str, SublevelInfo]:
    data = json.loads(content_path("levels.json").read_text(encoding="utf-8"))
    result: dict[str, SublevelInfo] = {}
    for item in data["sublevels"]:
        info = SublevelInfo(
            code=item["level"],
            title_ru=item["title_ru"],
            summary_ru=item.get("summary_ru", ""),
            vocab_target=int(item["vocab_target"]),
            can_do=item.get("can_do", {}),
            vocab_themes=item.get("vocab_themes", []),
        )
        Level(info.code)  # валидация
        result[info.code] = info
    missing = set(SUBLEVEL_CODES) - set(result)
    if missing:
        raise ValueError(f"В levels.json нет подуровней: {sorted(missing)}")
    return result
