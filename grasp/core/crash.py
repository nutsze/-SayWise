"""Перехват необработанных исключений.

Вместо молчаливого закрытия показываем окно «Что-то пошло не так»
с кнопкой «Скопировать отчёт». Сам диалог — в ``grasp.ui.crash_dialog``;
здесь только формирование отчёта и установка хуков.
"""

from __future__ import annotations

import logging
import platform
import sys
import threading
import traceback
from datetime import datetime
from typing import Callable

from grasp import __version__
from grasp.paths import logs_dir

log = logging.getLogger("grasp.crash")

ReportHandler = Callable[[str], None]
_handler: ReportHandler | None = None
_showing = False


def build_report(exc_type, exc_value, exc_tb) -> str:
    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion

        qt = f"PySide6 {pyside_version}, Qt {qVersion()}"
    except Exception:  # pragma: no cover
        qt = "Qt: недоступно"
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    return (
        f"Grasp {__version__}\n"
        f"Время: {datetime.now().isoformat(timespec='seconds')}\n"
        f"ОС: {platform.platform()}\n"
        f"Python: {sys.version.split()[0]} ({'frozen' if getattr(sys, 'frozen', False) else 'source'})\n"
        f"{qt}\n"
        f"Логи: {logs_dir()}\n"
        f"\n{tb}"
    )


def _excepthook(exc_type, exc_value, exc_tb) -> None:
    global _showing
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    report = build_report(exc_type, exc_value, exc_tb)
    log.critical("Необработанное исключение\n%s", report)
    if _handler is not None and not _showing:
        _showing = True
        try:
            _handler(report)
        except Exception:  # pragma: no cover - диалог не должен ронять приложение
            log.exception("Не удалось показать окно ошибки")
        finally:
            _showing = False


def _thread_hook(args: threading.ExceptHookArgs) -> None:
    report = build_report(args.exc_type, args.exc_value, args.exc_traceback)
    log.critical("Исключение в потоке %s\n%s", getattr(args.thread, "name", "?"), report)


def install(handler: ReportHandler | None = None) -> None:
    """Установить хуки. ``handler`` вызывается в GUI-потоке с текстом отчёта."""
    global _handler
    _handler = handler
    sys.excepthook = _excepthook
    threading.excepthook = _thread_hook
