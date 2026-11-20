"""Хранение API-ключа LLM через keyring.

На Windows это «Диспетчер учётных данных» (Credential Manager): ключ не
лежит в открытом виде ни в settings.json, ни в БД.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SERVICE = "Grasp"


class SecretStoreError(RuntimeError):
    """Хранилище недоступно (нет backend'а keyring и т. п.)."""


def _keyring():
    try:
        import keyring
        from keyring.errors import KeyringError  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise SecretStoreError("Модуль keyring недоступен") from exc
    return keyring


def _account(provider: str) -> str:
    return f"api-key:{provider}"


def set_api_key(provider: str, key: str) -> None:
    kr = _keyring()
    try:
        kr.set_password(SERVICE, _account(provider), key.strip())
    except Exception as exc:
        log.warning("Не удалось сохранить ключ: %s", exc)
        raise SecretStoreError(str(exc)) from exc


def get_api_key(provider: str) -> str | None:
    try:
        kr = _keyring()
        return kr.get_password(SERVICE, _account(provider))
    except Exception as exc:
        log.warning("Не удалось прочитать ключ: %s", exc)
        return None


def delete_api_key(provider: str) -> None:
    kr = _keyring()
    try:
        kr.delete_password(SERVICE, _account(provider))
    except Exception as exc:
        # PasswordDeleteError, если ключа и не было, — не ошибка для пользователя.
        log.info("Удаление ключа: %s", exc)


def has_api_key(provider: str) -> bool:
    return bool(get_api_key(provider))


def mask(key: str | None) -> str:
    if not key:
        return ""
    return key[:4] + "…" + key[-4:] if len(key) > 12 else "••••"
