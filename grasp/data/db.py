"""Подключение к БД и автоматический прогон миграций при старте."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker

from grasp.core.levels import SKILLS
from grasp.data.models import SkillProgress, UserProfile
from grasp.paths import database_path, resource_path

log = logging.getLogger(__name__)


def make_engine(db_path: Path | None = None) -> Engine:
    db_path = db_path or database_path()
    # URL.create, а не f"sqlite:///{path}": путь не экранируется вручную, и
    # символы вроде «%» или «#» в имени пользователя Windows не ломают его.
    engine = create_engine(URL.create("sqlite", database=str(db_path)), future=True)

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record) -> None:  # pragma: no cover - тривиально
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


def alembic_config(engine: Engine) -> Config:
    """Конфиг Alembic без alembic.ini — работает и из собранного EXE."""
    cfg = Config()
    # Путь не должен содержать «%»: Config — это configparser с интерполяцией.
    cfg.set_main_option("script_location", str(resource_path("data", "migrations")).replace("%", "%%"))
    # URL базы в конфиг НЕ кладём: на Windows он выглядит как
    # sqlite:///C%3A/Users/..., и configparser падает на «%». Движок
    # передаётся в env.py напрямую.
    cfg.attributes["engine"] = engine
    cfg.attributes["configure_logger"] = False
    return cfg


def upgrade(engine: Engine) -> None:
    command.upgrade(alembic_config(engine), "head")


@dataclass
class Database:
    engine: Engine
    session_factory: sessionmaker[Session]

    def session(self) -> Session:
        return self.session_factory()


def open_database(db_path: Path | None = None) -> Database:
    engine = make_engine(db_path)
    upgrade(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = Database(engine, factory)
    ensure_profile(db)
    log.info("БД открыта: %s", engine.url)
    return db


def ensure_profile(db: Database) -> UserProfile:
    with db.session() as s:
        profile = s.scalar(select(UserProfile).limit(1))
        if profile is None:
            profile = UserProfile(current_level="A1.1")
            profile.skills = [SkillProgress(skill=k, level="A1.1") for k in SKILLS]
            s.add(profile)
            s.commit()
        return profile


def get_profile(db: Database) -> UserProfile:
    with db.session() as s:
        profile = s.scalar(select(UserProfile).limit(1))
        assert profile is not None
        _ = list(profile.skills)  # загрузить до закрытия сессии
        return profile
