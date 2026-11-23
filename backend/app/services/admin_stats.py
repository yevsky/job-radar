"""Numbers for the admin dashboard. Everything is counted in the database."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Date, Select, cast, func, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models import AiAnalysis, Application, Conversation, JobOffer, Role, SearchRun, User
from app.models.enums import ApplicationStatus
from app.models.role import RoleName
from app.schemas.admin import AdminStats, DayCount

SEARCH_DAYS = 14
SIGNUP_WEEKS = 8


def _count(db: Session, query: Select[tuple[int]]) -> int:
    return db.scalar(query) or 0


def _per_day(
    db: Session, column: InstrumentedAttribute[datetime], since: datetime
) -> dict[date, int]:
    """How many rows have `column` on each UTC day since `since`."""
    day = cast(func.timezone('UTC', column), Date)
    rows = db.execute(select(day, func.count()).where(column >= since).group_by(day)).all()
    return {row[0]: row[1] for row in rows}


def searches_by_day(db: Session, today: date) -> list[DayCount]:
    first = today - timedelta(days=SEARCH_DAYS - 1)
    counts = _per_day(db, SearchRun.created_at, datetime.combine(first, datetime.min.time(), UTC))
    return [
        DayCount(day=first + timedelta(days=i), count=counts.get(first + timedelta(days=i), 0))
        for i in range(SEARCH_DAYS)
    ]


def signups_by_week(db: Session, today: date) -> list[DayCount]:
    """New accounts per week; each week starts on a Monday."""
    this_monday = today - timedelta(days=today.weekday())
    first = this_monday - timedelta(weeks=SIGNUP_WEEKS - 1)
    per_day = _per_day(db, User.created_at, datetime.combine(first, datetime.min.time(), UTC))
    weeks = {first + timedelta(weeks=i): 0 for i in range(SIGNUP_WEEKS)}
    for day, count in per_day.items():
        weeks[day - timedelta(days=day.weekday())] += count
    return [DayCount(day=monday, count=count) for monday, count in weeks.items()]


def get_admin_stats(db: Session, now: datetime | None = None) -> AdminStats:
    now = now or datetime.now(UTC)
    today = now.date()
    midnight = datetime.combine(today, datetime.min.time(), UTC)
    week_ago = now - timedelta(days=7)
    count = select(func.count())

    public = count.select_from(JobOffer).where(JobOffer.owner_id.is_(None))
    rows = db.execute(select(Application.status, func.count()).group_by(Application.status))
    by_status: dict[ApplicationStatus, int] = dict(rows.tuples().all())

    return AdminStats(
        users=_count(db, count.select_from(User)),
        admins=_count(db, count.select_from(User).join(Role).where(Role.name == RoleName.ADMIN)),
        new_users_last_7_days=_count(
            db, count.select_from(User).where(User.created_at >= week_ago)
        ),
        public_offers=_count(db, public.where(JobOffer.is_active)),
        hidden_offers=_count(db, public.where(JobOffer.is_active.is_(False))),
        private_offers=_count(
            db, count.select_from(JobOffer).where(JobOffer.owner_id.is_not(None))
        ),
        applications=sum(by_status.values()),
        applications_by_status={s: by_status.get(s, 0) for s in ApplicationStatus},
        searches_today=_count(
            db, count.select_from(SearchRun).where(SearchRun.created_at >= midnight)
        ),
        searches_last_7_days=_count(
            db, count.select_from(SearchRun).where(SearchRun.created_at >= week_ago)
        ),
        analyses=_count(db, count.select_from(AiAnalysis)),
        conversations=_count(db, count.select_from(Conversation)),
        searches_by_day=searches_by_day(db, today),
        signups_by_week=signups_by_week(db, today),
    )
