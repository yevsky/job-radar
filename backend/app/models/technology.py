from sqlalchemy import Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Technology(Base):
    __tablename__ = 'technologies'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)


user_technologies = Table(
    'user_technologies',
    Base.metadata,
    Column('user_id', ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('technology_id', ForeignKey('technologies.id', ondelete='CASCADE'), primary_key=True),
)
