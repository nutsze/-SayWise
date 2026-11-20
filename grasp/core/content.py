"""Загрузка учебного контента из JSON (``grasp/content``).

Контент не зашит в код. У каждой единицы (правило, слово, задание) есть
поле ``level`` — код подуровня (``"B1.2"``). Здесь — общая загрузка
и проверка этого поля; полноценные модели правил/заданий появятся
на шагах 2–4.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from grasp.core.levels import SUBLEVEL_CODES, Level, is_valid_level
from grasp.paths import content_path


class ContentError(ValueError):
    pass


def read_json(*parts: str) -> Any:
    path = content_path(*parts)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContentError(f"{path}: {exc}") from exc


def iter_content_files() -> Iterator[Path]:
    root = content_path()
    yield from sorted(root.rglob("*.json"))


def iter_level_fields(node: Any, where: str = "") -> Iterator[tuple[str, Any]]:
    """Все значения полей ``level`` в дереве JSON (для валидации)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "level":
                yield where or "/", value
            else:
                yield from iter_level_fields(value, f"{where}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from iter_level_fields(value, f"{where}[{i}]")


def validate_levels() -> list[str]:
    """Список ошибок: неизвестные коды в полях ``level``."""
    errors: list[str] = []
    for path in iter_content_files():
        data = json.loads(path.read_text(encoding="utf-8"))
        for where, value in iter_level_fields(data):
            if not isinstance(value, str) or not is_valid_level(value):
                errors.append(f"{path.name}{where}: level={value!r}")
    return errors


# --- грамматика: индекс тем ----------------------------------------------


@dataclass
class RuleRef:
    id: str
    title: str
    level: str
    topic_id: str


@dataclass
class Topic:
    id: str
    title_ru: str
    title_en: str
    summary_ru: str
    rules: list[RuleRef] = field(default_factory=list)

    @property
    def level_range(self) -> tuple[str, str]:
        levels = sorted((Level(r.level) for r in self.rules))
        return levels[0].code, levels[-1].code


@lru_cache(maxsize=1)
def load_topics() -> list[Topic]:
    data = read_json("grammar", "topics.json")
    topics: list[Topic] = []
    for t in data["topics"]:
        topic = Topic(t["id"], t["title_ru"], t["title_en"], t.get("summary_ru", ""))
        for r in t["rules"]:
            if not is_valid_level(r["level"]):
                raise ContentError(f"{t['id']}/{r['id']}: неверный level {r['level']!r}")
            topic.rules.append(RuleRef(r["id"], r["title"], r["level"], topic.id))
        topic.rules.sort(key=lambda r: Level(r.level).index)
        topics.append(topic)
    return topics


def rules_by_level() -> dict[str, list[RuleRef]]:
    """Маршрут «По уровням»: правила из всех тем, сгруппированные по ступеням."""
    result: dict[str, list[RuleRef]] = {code: [] for code in SUBLEVEL_CODES}
    for topic in load_topics():
        for rule in topic.rules:
            result[rule.level].append(rule)
    return result


@lru_cache(maxsize=1)
def load_vocabulary() -> list[dict]:
    words: list[dict] = []
    folder = content_path("vocabulary")
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        words.extend(data.get("words", []))
    return words
