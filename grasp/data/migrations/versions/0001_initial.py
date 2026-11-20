"""Начальная схема: профиль и прогресс по навыкам.

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("current_level", sa.String(length=8), nullable=False, server_default="A1.1"),
        sa.Column("level_progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("placement_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "skill_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "profile_id",
            sa.Integer(),
            sa.ForeignKey("user_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("skill", sa.String(length=16), nullable=False),
        sa.Column("level", sa.String(length=8), nullable=False, server_default="A1.1"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("profile_id", "skill"),
    )


def downgrade() -> None:
    op.drop_table("skill_progress")
    op.drop_table("user_profile")
