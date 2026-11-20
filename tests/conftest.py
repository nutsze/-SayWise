"""Общая настройка тестов: offscreen-Qt и отдельная папка данных."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# До любого импорта Qt/grasp.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["GRASP_DATA_DIR"] = tempfile.mkdtemp(prefix="grasp-tests-")
os.environ["GRASP_INSTANCE_NAME"] = f"grasp-tests-{os.getpid()}"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402


class MemoryKeyring:
    """Keyring-backend в памяти (на CI нет системного хранилища)."""

    priority = 100

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


@pytest.fixture(autouse=True)
def memory_keyring(monkeypatch):
    import keyring

    backend = MemoryKeyring()
    monkeypatch.setattr(keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keyring, "delete_password", backend.delete_password)
    return backend


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Чистая папка пользовательских данных на один тест."""
    from grasp import paths

    monkeypatch.setenv("GRASP_DATA_DIR", str(tmp_path / "data"))
    paths.reset_caches()
    yield tmp_path / "data"
    paths.reset_caches()


@pytest.fixture
def ui(qapp, data_dir):
    """Главное окно на свежих данных. Возвращает (ctx, window)."""
    from grasp.app import build_ui
    from grasp.core.settings import Settings

    ctx, window = build_ui(qapp, settings=Settings(theme="light"))
    yield ctx, window
    window.close()
    window.deleteLater()
    ctx.db.engine.dispose()


@pytest.fixture(scope="session")
def qapp_cls():
    from PySide6.QtWidgets import QApplication

    return QApplication


@pytest.fixture(scope="session")
def qapp(qapp_args, qapp_cls, pytestconfig):
    from grasp.app import create_application

    return create_application(qapp_args or [sys.argv[0]])
