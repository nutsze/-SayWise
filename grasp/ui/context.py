"""Общее состояние, которое главное окно передаёт экранам."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from grasp.core.settings import Settings, save_settings
from grasp.data.db import Database
from grasp.ui.theme import ThemeManager


@dataclass
class AppContext:
    settings: Settings
    db: Database
    themes: ThemeManager
    on_font_scale: Callable[[int], None] = field(default=lambda _v: None)
    navigate: Callable[[str], None] = field(default=lambda _k: None)

    def save(self) -> None:
        save_settings(self.settings)
