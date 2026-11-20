"""БД, миграции Alembic и загрузка модели речи."""

from __future__ import annotations

import http.server
import threading
from functools import partial

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from grasp.core import model_download as md
from grasp.data.db import get_profile, open_database
from grasp.data.models import Base


def test_migrations_create_schema_and_profile(data_dir):
    db = open_database()
    tables = set(inspect(db.engine).get_table_names())
    assert {"user_profile", "skill_progress", "alembic_version"} <= tables
    profile = get_profile(db)
    assert profile.current_level == "A1.1"
    assert {s.skill for s in profile.skills} == {"reading", "listening", "writing", "speaking"}
    db.engine.dispose()


def test_migrations_match_models(data_dir):
    """Модели и миграции не разошлись (иначе нужна новая ревизия Alembic)."""
    db = open_database()
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    db.engine.dispose()
    assert diff == []


def test_db_path_with_percent(tmp_path):
    """Регрессия: на Windows URL БД содержит «C%3A», configparser Alembic падал."""
    folder = tmp_path / "100% C%3A data"
    folder.mkdir()
    db = open_database(folder / "grasp.db")
    assert get_profile(db).current_level == "A1.1"
    db.engine.dispose()


def test_progress_survives_reopen(data_dir):
    db = open_database()
    with db.session() as s:
        from grasp.data.models import UserProfile

        p = s.query(UserProfile).first()
        p.current_level = "B1.2"
        s.commit()
    db.engine.dispose()
    db2 = open_database()
    assert get_profile(db2).current_level == "B1.2"
    db2.engine.dispose()


# --- загрузка модели ----------------------------------------------------------------


@pytest.fixture
def file_server(tmp_path):
    root = tmp_path / "srv"
    root.mkdir()
    for name in md.MODEL_FILES:
        (root / name).write_bytes(name.encode() * 5000)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_model_download_with_progress(data_dir, file_server):
    info = md.ModelInfo("base")
    seen = []
    md.download_model(info, lambda d, t, n: seen.append((d, t)), url_for=lambda f: f"{file_server}/{f}")
    assert info.is_installed
    assert seen and seen[-1][0] == seen[-1][1]
    assert not list(info.folder.glob("*.part"))


def test_model_download_cancel_leaves_no_partial(data_dir, file_server):
    info = md.ModelInfo("small")
    with pytest.raises(md.DownloadCancelled):
        md.download_model(info, is_cancelled=lambda: True, url_for=lambda f: f"{file_server}/{f}")
    assert not info.is_installed
    assert not list(info.folder.glob("*.part"))


def test_model_download_offline_message(data_dir):
    info = md.ModelInfo("base")
    with pytest.raises(md.DownloadError) as exc:
        md.download_model(info, url_for=lambda f: f"http://127.0.0.1:9/{f}", timeout=2)
    assert "интернет" in str(exc.value)
