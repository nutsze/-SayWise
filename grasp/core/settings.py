"""Настройки пользователя (``%APPDATA%\\Grasp\\settings.json``).

API-ключ здесь НЕ хранится — только в keyring (см. :mod:`grasp.core.secrets`).
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from grasp.paths import settings_path

log = logging.getLogger(__name__)

THEME_MODES = ("system", "light", "dark")
WINDOW_STATES = ("normal", "maximized", "fullscreen")
FONT_SCALE_MIN = 70
FONT_SCALE_MAX = 200
FONT_SCALE_STEP = 10
GOALS = ("toefl", "general")
TTS_ENGINES = ("edge", "offline")
STT_ENGINES = ("local", "api")
STT_MODELS = ("base", "small")


@dataclass
class Settings:
    theme: str = "system"
    font_scale: int = 100  # % поверх системного масштаба Windows
    window_geometry: str = ""  # base64 от QWidget.saveGeometry()
    window_state: str = "normal"
    last_page: str = "home"
    grammar_view: str = "topics"  # topics | levels

    ai_provider: str = "anthropic"
    goal: str = "toefl"
    target_toefl: float = 5.0
    exam_date: str = ""  # ISO yyyy-mm-dd
    minutes_per_day: int = 30

    tts_engine: str = "edge"
    stt_engine: str = "local"
    stt_model: str = "base"

    onboarding_done: bool = False
    extra: dict = field(default_factory=dict)

    def normalized(self) -> "Settings":
        """Привести значения к допустимым (на случай ручной правки файла)."""
        if self.theme not in THEME_MODES:
            self.theme = "system"
        if self.window_state not in WINDOW_STATES:
            self.window_state = "normal"
        try:
            self.font_scale = int(self.font_scale)
        except (TypeError, ValueError):
            self.font_scale = 100
        self.font_scale = max(FONT_SCALE_MIN, min(FONT_SCALE_MAX, self.font_scale))
        if self.goal not in GOALS:
            self.goal = "toefl"
        try:
            self.target_toefl = float(self.target_toefl)
        except (TypeError, ValueError):
            self.target_toefl = 5.0
        self.target_toefl = max(1.0, min(6.0, round(self.target_toefl * 2) / 2))
        try:
            self.minutes_per_day = int(self.minutes_per_day)
        except (TypeError, ValueError):
            self.minutes_per_day = 30
        self.minutes_per_day = max(5, min(240, self.minutes_per_day))
        if self.tts_engine not in TTS_ENGINES:
            self.tts_engine = "edge"
        if self.stt_engine not in STT_ENGINES:
            self.stt_engine = "local"
        if self.stt_model not in STT_MODELS:
            self.stt_model = "base"
        if self.grammar_view not in ("topics", "levels"):
            self.grammar_view = "topics"
        return self


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    if not path.exists():
        return Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.exception("Не удалось прочитать настройки, используются значения по умолчанию")
        return Settings()
    known = {f.name for f in fields(Settings)}
    data = {k: v for k, v in raw.items() if k in known}
    try:
        return Settings(**data).normalized()
    except TypeError:
        log.exception("Повреждённые настройки")
        return Settings()


def save_settings(settings: Settings, path: Path | None = None) -> None:
    """Атомарная запись: сначала во временный файл, затем замена."""
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(settings), ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except OSError:
        log.exception("Не удалось сохранить настройки")
        try:
            os.unlink(tmp)
        except OSError:
            pass
