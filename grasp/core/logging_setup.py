"""Логирование в ``%APPDATA%\\Grasp\\logs``."""

from __future__ import annotations

import faulthandler
import logging
import logging.handlers
import sys

from grasp.paths import logs_dir

LOG_FILE = "grasp.log"
FAULT_FILE = "native-crash.log"

_fault_stream = None


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if getattr(root, "_grasp_configured", False):
        return
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir() / LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    # В оконной сборке (без консоли) sys.stderr равен None.
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        console.setLevel(logging.WARNING)
        root.addHandler(console)

    # Падения в нативном коде (Qt, драйверы) — faulthandler в отдельный файл.
    global _fault_stream
    try:
        _fault_stream = open(logs_dir() / FAULT_FILE, "a", encoding="utf-8")  # noqa: SIM115
        faulthandler.enable(_fault_stream)
    except (OSError, RuntimeError):
        pass

    root._grasp_configured = True  # type: ignore[attr-defined]
