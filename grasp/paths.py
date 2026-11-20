"""Пути к ресурсам и к пользовательским данным.

* Ресурсы (шрифты, иконки, темы, учебный контент, миграции) лежат внутри
  пакета ``grasp`` и упаковываются в сборку. :func:`resource_path` работает
  и из исходников, и из собранного EXE (PyInstaller ``sys._MEIPASS``,
  Nuitka ``__compiled__``).
* Пользовательские данные (БД, настройки, логи, записи голоса, модели) —
  в ``%APPDATA%\\Grasp`` на Windows. Никогда рядом с EXE: в Program Files
  нет прав на запись, а обновление стёрло бы прогресс.
  Исключение — портативная версия: рядом с EXE лежит файл ``portable.flag``,
  данные хранятся в соседней папке ``GraspData`` (если в неё можно писать).
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

APP_DIR_NAME = "Grasp"
PORTABLE_FLAG = "portable.flag"
PORTABLE_DATA_DIR = "GraspData"


def is_frozen() -> bool:
    """True, если приложение запущено из собранного EXE."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


@lru_cache(maxsize=1)
def package_root() -> Path:
    """Корень пакета ``grasp`` (папка, где лежат resources/ и content/)."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "grasp"
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Абсолютный путь к ресурсу внутри пакета/сборки.

    >>> resource_path("resources", "fonts", "NotoSans-Regular.ttf")
    """
    return package_root().joinpath(*parts)


def content_path(*parts: str) -> Path:
    return resource_path("content", *parts)


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return package_root().parent


def _is_writable(directory: Path) -> bool:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _default_user_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIR_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / APP_DIR_NAME


@lru_cache(maxsize=1)
def user_data_dir() -> Path:
    """Папка пользовательских данных (создаётся при первом обращении).

    Порядок: переменная окружения ``GRASP_DATA_DIR`` (тесты, отладка) →
    портативный режим → ``%APPDATA%\\Grasp``.
    """
    override = os.environ.get("GRASP_DATA_DIR")
    if override:
        path = Path(override)
    else:
        path = _default_user_dir()
        if is_frozen() and (executable_dir() / PORTABLE_FLAG).exists():
            portable = executable_dir() / PORTABLE_DATA_DIR
            if _is_writable(portable):
                path = portable
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def recordings_dir() -> Path:
    path = user_data_dir() / "recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def models_dir() -> Path:
    path = user_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return user_data_dir() / "grasp.db"


def settings_path() -> Path:
    return user_data_dir() / "settings.json"


def reset_caches() -> None:
    """Сбросить кэш путей (для тестов, меняющих GRASP_DATA_DIR)."""
    user_data_dir.cache_clear()
    package_root.cache_clear()
