from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserPreferredLocation(Base):
    __tablename__ = 'user_preferred_locations'

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    location: Mapped[str] = mapped_column(String(100), primary_key=True)

    user: Mapped['User'] = relationship(back_populates='preferred_locations')
