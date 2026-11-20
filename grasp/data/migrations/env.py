"""Окружение Alembic.

Запускается двумя способами:
* из приложения (``grasp.data.db.upgrade``) — engine передаётся через
  ``config.attributes["engine"]``;
* из командной строки разработчика: ``alembic revision --autogenerate -m "..."``
  (см. alembic.ini в корне репозитория).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from grasp.data.models import Base

config = context.config
if config.config_file_name and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = config.attributes.get("engine")
    if engine is None:
        if config.get_main_option("sqlalchemy.url"):
            engine = engine_from_config(
                config.get_section(config.config_ini_section, {}),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
        else:  # alembic из командной строки: БД пользователя
            from grasp.data.db import make_engine

            engine = make_engine()
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite не умеет ALTER COLUMN
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
