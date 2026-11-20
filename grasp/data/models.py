"""ORM-модели. Схема меняется только через миграции Alembic."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserProfile(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    current_level: Mapped[str] = mapped_column(String(8), default="A1.1", nullable=False)
    # Прогресс до следующей ступени, 0..1
    level_progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    placement_done: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    skills: Mapped[list["SkillProgress"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class SkillProgress(Base):
    """Подуровень и прогресс отдельно по Reading/Listening/Writing/Speaking."""

    __tablename__ = "skill_progress"
    __table_args__ = (UniqueConstraint("profile_id", "skill"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("user_profile.id", ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(String(16), nullable=False)
    level: Mapped[str] = mapped_column(String(8), default="A1.1", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    profile: Mapped[UserProfile] = relationship(back_populates="skills")
