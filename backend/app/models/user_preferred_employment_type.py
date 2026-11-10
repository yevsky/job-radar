from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EmploymentType

if TYPE_CHECKING:
    from app.models.user import User


class UserPreferredEmploymentType(Base):
    __tablename__ = 'user_preferred_employment_types'

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), primary_key=True
    )
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(
            EmploymentType, name='employment_type', values_callable=lambda e: [m.value for m in e]
        ),
        primary_key=True,
    )

    user: Mapped['User'] = relationship(back_populates='preferred_employment_types')
