from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EmploymentType, ExperienceLevel, SourceKind

if TYPE_CHECKING:
    from app.models.technology import Technology


job_offer_technologies = Table(
    'job_offer_technologies',
    Base.metadata,
    Column('job_offer_id', ForeignKey('job_offers.id', ondelete='CASCADE'), primary_key=True),
    Column('technology_id', ForeignKey('technologies.id', ondelete='CASCADE'), primary_key=True),
)


class JobOffer(Base):
    __tablename__ = 'job_offers'
    __table_args__ = (
        # One public offer per URL (owner_id NULL), and one private copy per user.
        UniqueConstraint(
            'owner_id', 'url', name='uq_job_offers_owner_id_url', postgresql_nulls_not_distinct=True
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, name='source_kind', values_callable=lambda e: [m.value for m in e])
    )
    location: Mapped[str | None] = mapped_column(String(100), index=True)
    employment_type: Mapped[EmploymentType | None] = mapped_column(
        Enum(
            EmploymentType, name='employment_type', values_callable=lambda e: [m.value for m in e]
        ),
        index=True,
    )
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        Enum(
            ExperienceLevel, name='experience_level', values_callable=lambda e: [m.value for m in e]
        ),
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true(), index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    technologies: Mapped[list['Technology']] = relationship(secondary=job_offer_technologies)
