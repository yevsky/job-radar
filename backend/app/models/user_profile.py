from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ExperienceLevel

if TYPE_CHECKING:
    from app.models.user import User


class UserProfile(Base):
    __tablename__ = 'user_profiles'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), unique=True)
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    bio: Mapped[str | None] = mapped_column(Text)
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        Enum(
            ExperienceLevel, name='experience_level', values_callable=lambda e: [m.value for m in e]
        )
    )
    desired_position: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped['User'] = relationship(back_populates='profile')
