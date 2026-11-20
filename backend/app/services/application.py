"""Applications, saved offers and the calendar.

A saved offer is an application with status 'saved'. Every status an application gets is also
written to 'application_status_changes', which the history and the calendar read.
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, ApplicationStatusChange, JobOffer
from app.models.enums import ApplicationStatus
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    CalendarEvent,
    CalendarEventKind,
    SavedJobRead,
    StatusChangeRead,
)
from app.services.job_offer import to_list_item, visible_to

SAVED = ApplicationStatus.SAVED


class ApplicationNotFoundError(Exception):
    """No such application, or it belongs to someone else."""


class OfferNotFoundError(Exception):
    """The offer doesn't exist, or it is someone else's private offer."""


class NotSavedError(Exception):
    """The offer isn't saved (no application, or it has moved past `saved`)."""


def to_read(application: Application) -> ApplicationRead:
    return ApplicationRead(
        id=application.id,
        job_offer=to_list_item(application.job_offer),
        status=application.status,
        resume_id=application.resume_id,
        notes=application.notes,
        applied_at=application.applied_at,
        interview_at=application.interview_at,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def to_saved(application: Application) -> SavedJobRead:
    return SavedJobRead(
        id=application.id,
        job_offer=to_list_item(application.job_offer),
        created_at=application.created_at,
    )


def _owned(user_id: int) -> Select[tuple[Application]]:
    """The user's applications, with the offer, its technologies and the history loaded."""
    return (
        select(Application)
        .where(Application.user_id == user_id)
        .options(
            selectinload(Application.job_offer).selectinload(JobOffer.technologies),
            selectinload(Application.status_changes),
        )
    )


def list_applications(
    db: Session, user_id: int, status: ApplicationStatus | None = None
) -> Sequence[Application]:
    query = _owned(user_id)
    if status is not None:
        query = query.where(Application.status == status)
    return db.scalars(query.order_by(Application.updated_at.desc(), Application.id.desc())).all()


def get_application(db: Session, user_id: int, application_id: int) -> Application:
    application = db.scalar(_owned(user_id).where(Application.id == application_id))
    if application is None:
        raise ApplicationNotFoundError
    return application


def get_history(db: Session, user_id: int, application_id: int) -> list[StatusChangeRead]:
    application = get_application(db, user_id, application_id)
    return [
        StatusChangeRead(status=c.status, changed_at=c.changed_at)
        for c in application.status_changes
    ]


def _record(application: Application, status: ApplicationStatus, at: datetime) -> None:
    application.status = status
    application.status_changes.append(ApplicationStatusChange(status=status, changed_at=at))


def create_application(
    db: Session, user_id: int, data: ApplicationCreate
) -> tuple[Application, bool]:
    """Start tracking an offer. Returns (application, created); an existing one comes back as is."""
    offer = db.scalar(select(JobOffer).where(JobOffer.id == data.job_offer_id, visible_to(user_id)))
    if offer is None:
        raise OfferNotFoundError

    existing = db.scalar(_owned(user_id).where(Application.job_offer_id == offer.id))
    if existing is not None:
        return existing, False

    now = datetime.now(UTC)
    application = Application(
        user_id=user_id,
        job_offer=offer,
        resume_id=data.resume_id,
        notes=data.notes,
        applied_at=None if data.status == SAVED else (data.applied_at or now),
        created_at=now,
        updated_at=now,
    )
    _record(application, data.status, now)
    db.add(application)
    db.commit()
    return get_application(db, user_id, application.id), True


def update_application(
    db: Session, user_id: int, application_id: int, data: ApplicationUpdate
) -> Application:
    """Change the fields that were sent. A new status is added to the history."""
    application = get_application(db, user_id, application_id)
    sent = data.model_fields_set
    now = datetime.now(UTC)

    if 'resume_id' in sent:
        application.resume_id = data.resume_id
    if 'notes' in sent:
        application.notes = data.notes
    if 'applied_at' in sent:
        application.applied_at = data.applied_at
    if 'interview_at' in sent:
        application.interview_at = data.interview_at

    if data.status is not None and data.status != application.status:
        _record(application, data.status, now)
        # Moving a saved offer on is the moment the user applied.
        if data.status != SAVED and application.applied_at is None:
            application.applied_at = now

    application.updated_at = now
    db.commit()
    return get_application(db, user_id, application_id)


def delete_application(db: Session, user_id: int, application_id: int) -> None:
    db.delete(get_application(db, user_id, application_id))
    db.commit()


def list_saved(db: Session, user_id: int) -> list[SavedJobRead]:
    rows = db.scalars(
        _owned(user_id)
        .where(Application.status == SAVED)
        .order_by(Application.created_at.desc(), Application.id.desc())
    ).all()
    return [to_saved(row) for row in rows]


def save_offer(db: Session, user_id: int, job_offer_id: int) -> tuple[SavedJobRead, bool]:
    """Save an offer. If it already has an application (saved or further), that one is returned."""
    application, created = create_application(
        db, user_id, ApplicationCreate(job_offer_id=job_offer_id, status=SAVED)
    )
    return to_saved(application), created


def unsave_offer(db: Session, user_id: int, job_offer_id: int) -> None:
    """Remove a saved offer. An offer the user already applied to is not touched."""
    application = db.scalar(
        select(Application).where(
            Application.user_id == user_id,
            Application.job_offer_id == job_offer_id,
            Application.status == SAVED,
        )
    )
    if application is None:
        raise NotSavedError
    db.delete(application)
    db.commit()


def calendar(db: Session, user_id: int, start: date, end: date) -> list[CalendarEvent]:
    """Applied dates, status changes, interviews and offer deadlines between two days (UTC)."""

    def inside(moment: datetime | None) -> bool:
        return moment is not None and start <= moment.astimezone(UTC).date() <= end

    events: list[CalendarEvent] = []
    for application in list_applications(db, user_id):
        offer = application.job_offer

        def event(
            moment: datetime,
            kind: CalendarEventKind,
            status: ApplicationStatus | None,
            with_time: bool = False,
            app: Application = application,
        ) -> CalendarEvent:
            utc = moment.astimezone(UTC)
            return CalendarEvent(
                date=utc.date(),
                kind=kind,
                title=app.job_offer.title,
                company_name=app.job_offer.company_name,
                job_offer_id=app.job_offer_id,
                application_id=app.id,
                status=status,
                time=utc.strftime('%H:%M') if with_time else None,
            )

        for change in application.status_changes:
            if change.status == SAVED or not inside(change.changed_at):
                continue
            if change.status == ApplicationStatus.APPLIED:
                events.append(event(change.changed_at, CalendarEventKind.APPLIED, change.status))
            elif change.status == ApplicationStatus.INTERVIEW and application.interview_at:
                continue  # shown once, at the interview's own date and time
            else:
                events.append(
                    event(change.changed_at, CalendarEventKind.STATUS_CHANGE, change.status)
                )

        if application.interview_at and inside(application.interview_at):
            events.append(
                event(
                    application.interview_at,
                    CalendarEventKind.INTERVIEW,
                    ApplicationStatus.INTERVIEW,
                    with_time=True,
                )
            )

        closed = application.status in (ApplicationStatus.REJECTED, ApplicationStatus.DECLINED)
        if offer.deadline and not closed and inside(offer.deadline):
            events.append(event(offer.deadline, CalendarEventKind.DEADLINE, None))

    return sorted(events, key=lambda e: (e.date, e.time or '', e.title))
