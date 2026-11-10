from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user_preferred_employment_type import UserPreferredEmploymentType
    from app.models.user_preferred_location import UserPreferredLocation
    from app.models.user_profile import UserProfile


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    role: Mapped['Role'] = relationship(back_populates='users')
    profile: Mapped['UserProfile | None'] = relationship(
        back_populates='user', cascade='all, delete-orphan'
    )
    preferred_locations: Mapped[list['UserPreferredLocation']] = relationship(
        back_populates='user', cascade='all, delete-orphan'
    )
    preferred_employment_types: Mapped[list['UserPreferredEmploymentType']] = relationship(
        back_populates='user', cascade='all, delete-orphan'
    )
