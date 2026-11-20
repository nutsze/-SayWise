"""Проверка доступа в интернет (для AI-проверки и онлайн-озвучки)."""

from __future__ import annotations

import socket

OFFLINE_MESSAGE = (
    "Нет подключения к интернету. AI-проверка и онлайн-озвучка недоступны — "
    "используется встроенный контент и офлайн-голос."
)


def is_online(host: str = "1.1.1.1", port: int = 443, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
