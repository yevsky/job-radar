from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ApplicationStatus

if TYPE_CHECKING:
    from app.models.job_offer import JobOffer

application_status_enum = Enum(
    ApplicationStatus, name='application_status', values_callable=lambda e: [m.value for m in e]
)


class Application(Base):
    """One user's progress on one offer. A saved offer is an application with status `saved`."""

    __tablename__ = 'applications'
    __table_args__ = (
        UniqueConstraint('user_id', 'job_offer_id', name='uq_applications_user_id_job_offer_id'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False
    )
    job_offer_id: Mapped[int] = mapped_column(
        ForeignKey('job_offers.id', ondelete='CASCADE'), index=True, nullable=False
    )
    status: Mapped[ApplicationStatus] = mapped_column(application_status_enum, nullable=False)
    # Which CV was sent; becomes a foreign key when the resumes table exists (milestone 8).
    resume_id: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    job_offer: Mapped['JobOffer'] = relationship()
    status_changes: Mapped[list['ApplicationStatusChange']] = relationship(
        back_populates='application',
        cascade='all, delete-orphan',
        order_by='ApplicationStatusChange.changed_at, ApplicationStatusChange.id',
    )


class ApplicationStatusChange(Base):
    """One row per status an application got, with the time it changed (for history and stats)."""

    __tablename__ = 'application_status_changes'

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey('applications.id', ondelete='CASCADE'), index=True, nullable=False
    )
    status: Mapped[ApplicationStatus] = mapped_column(application_status_enum, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    application: Mapped[Application] = relationship(back_populates='status_changes')
