"""Applications, saved offers, the calendar and the dashboard stats.

A saved offer is an application with status `saved`. Every status an application gets is also
written to `application_status_changes`, which the history, the calendar and the stats read.
"""

from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.models import Application, ApplicationStatusChange, JobOffer
from app.models.enums import ApplicationStatus
from app.schemas.application import (
    FUNNEL_STAGES,
    ApplicationCreate,
    ApplicationRead,
    ApplicationStats,
    ApplicationUpdate,
    CalendarEvent,
    CalendarEventKind,
    FunnelStep,
    Outcome,
    SavedJobRead,
    StaleItem,
    StaleStage,
    StatsRange,
    StatusChangeRead,
    WeeklyCount,
)
from app.services.job_offer import to_list_item, visible_to

SAVED = ApplicationStatus.SAVED
RANGE_DAYS = {'30d': 30, '90d': 90}

# A reply is the company moving the application on, good or bad. Declining and accepting are the
# user's own steps, but reaching `accepted` means an offer came first, so it counts too.
REPLY_STATUSES = frozenset(
    {
        ApplicationStatus.SCREENING,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.OFFER,
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
    }
)

# Stale after this many days in the same status (interviews: days after the interview itself).
STALE_AFTER_DAYS: dict[ApplicationStatus, int] = {
    ApplicationStatus.SAVED: 7,
    ApplicationStatus.APPLIED: 10,
    ApplicationStatus.SCREENING: 10,
    ApplicationStatus.INTERVIEW: 7,
    ApplicationStatus.OFFER: 3,
}


class ApplicationNotFoundError(Exception):
    """No such application, or it belongs to someone else."""


class OfferNotFoundError(Exception):
    """The offer doesn't exist, or it is someone else's private offer."""


class NotSavedError(Exception):
    """The offer isn't saved (no application, or it has moved past `saved`)."""


# ---- reading -------------------------------------------------------------------------------


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
        status=application.status,
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


# ---- writing -------------------------------------------------------------------------------


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


# ---- saved offers (a shortcut over applications with status `saved`) -----------------------


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


def unsave_offer(db: Session, user_id: int, job_offer_id: int) -> bool:
    """Remove a saved offer. An offer the user already applied to is not touched.

    A private offer the user added (kept from a search, sent from the browser, added by
    hand) is deleted with it: nothing else keeps it, so its analyses and summary go too
    (the foreign keys cascade). A public offer stays for everyone else. Returns True when
    the offer itself was deleted.
    """
    application = db.scalar(
        select(Application).where(
            Application.user_id == user_id,
            Application.job_offer_id == job_offer_id,
            Application.status == SAVED,
        )
    )
    if application is None:
        raise NotSavedError
    offer = db.get(JobOffer, job_offer_id)
    deleted = offer is not None and offer.owner_id == user_id
    db.delete(offer if deleted else application)
    db.commit()
    return deleted


# ---- calendar ------------------------------------------------------------------------------


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


# ---- stats ---------------------------------------------------------------------------------


def _applied_at(application: Application) -> datetime | None:
    """When the user applied: the stored date, else the first status past `saved`."""
    if application.applied_at:
        return application.applied_at
    for change in application.status_changes:
        if change.status != SAVED:
            return change.changed_at
    return None


def first_reply_at(application: Application) -> datetime | None:
    """When the company first answered: the first reply status after the user applied."""
    applied = _applied_at(application)
    if applied is None:
        return None
    for change in application.status_changes:
        if change.status in REPLY_STATUSES and change.changed_at >= applied:
            return change.changed_at
    return None


def _furthest_stage(application: Application) -> int:
    """Index in FUNNEL_STAGES of the furthest stage the history reached (0 = applied)."""
    reached = [
        FUNNEL_STAGES.index(c.status)
        for c in application.status_changes
        if c.status in FUNNEL_STAGES
    ]
    return max(reached, default=0)


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def stats(
    db: Session, user_id: int, range_: StatsRange, now: datetime | None = None
) -> ApplicationStats:
    """Funnel, outcomes and weekly counts for the applications sent in the range."""
    now = now or datetime.now(UTC)
    since = now - timedelta(days=RANGE_DAYS[range_]) if range_ in RANGE_DAYS else None
    applications = list_applications(db, user_id)

    sent = [
        (a, at)
        for a in applications
        if (at := _applied_at(a)) is not None and (since is None or at >= since)
    ]

    reached = [_furthest_stage(a) for a, _ in sent]
    funnel = [
        FunnelStep(stage=stage, reached=sum(1 for r in reached if r >= i))
        for i, stage in enumerate(FUNNEL_STAGES)
    ]

    counts: Counter[tuple[ApplicationStatus, ApplicationStatus]] = Counter()
    for (application, _), stage_index in zip(sent, reached, strict=True):
        stage = FUNNEL_STAGES[stage_index]
        if stage != ApplicationStatus.ACCEPTED:
            counts[(stage, application.status)] += 1
    order = list(ApplicationStatus)
    outcomes = [
        Outcome(stage=stage, status=status, count=count)
        for (stage, status), count in sorted(
            counts.items(), key=lambda item: (order.index(item[0][0]), order.index(item[0][1]))
        )
    ]

    saved_times = [
        c.changed_at for a in applications for c in a.status_changes if c.status == SAVED
    ]
    applied_times = [at for a in applications if (at := _applied_at(a)) is not None]
    reply_times = [at for a in applications if (at := first_reply_at(a)) is not None]
    moments = [*saved_times, *applied_times]

    weekly: list[WeeklyCount] = []
    if since is not None or moments:
        first = since or min(moments)
        week = _monday(first.astimezone(UTC).date())
        last = _monday(now.astimezone(UTC).date())
        while week <= last:
            start = datetime.combine(week, time.min, tzinfo=UTC)
            end = start + timedelta(days=7)
            weekly.append(
                WeeklyCount(
                    week_start=week,
                    saved=sum(1 for t in saved_times if start <= t < end),
                    applied=sum(1 for t in applied_times if start <= t < end),
                    replied=sum(1 for t in reply_times if start <= t < end),
                )
            )
            week += timedelta(days=7)

    replied = sum(1 for a, _ in sent if first_reply_at(a) is not None)
    return ApplicationStats(
        range=range_, funnel=funnel, outcomes=outcomes, weekly=weekly, replied=replied
    )


# ---- stale ---------------------------------------------------------------------------------


def _in_status_since(application: Application) -> datetime:
    """When the application got its current status (the last change to it)."""
    for change in reversed(application.status_changes):
        if change.status == application.status:
            return change.changed_at
    return application.updated_at


def stale(db: Session, user_id: int, now: datetime | None = None) -> list[StaleStage]:
    """For each open status, how many applications sit in it and which have waited too long.

    An interview still ahead isn't stale; one that happened counts from the interview day.
    """
    now = now or datetime.now(UTC)
    applications = list_applications(db, user_id)
    stages: list[StaleStage] = []
    for stage, after_days in STALE_AFTER_DAYS.items():
        in_stage = [a for a in applications if a.status == stage]
        items: list[StaleItem] = []
        for application in in_stage:
            since = _in_status_since(application)
            if stage == ApplicationStatus.INTERVIEW and application.interview_at is not None:
                if application.interview_at > now:
                    continue
                since = max(since, application.interview_at)
            days = (now - since).days
            if days >= after_days:
                offer = application.job_offer
                items.append(
                    StaleItem(
                        application_id=application.id,
                        job_offer_id=offer.id,
                        title=offer.title,
                        company_name=offer.company_name,
                        since=since,
                        days=days,
                    )
                )
        items.sort(key=lambda item: (-item.days, item.application_id))
        stages.append(
            StaleStage(stage=stage, after_days=after_days, total=len(in_stage), items=items)
        )
    return stages
