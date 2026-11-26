"""Create a demo account with a filled profile and two months of job search history
(run with `just seed-demo`), for screenshots and presentations.

Every date is relative to today, so the dashboard, the calendar and the stale card always
look current. Running it again deletes the demo account and creates it anew. The public
offers come from `just seed`; they are loaded first if the board is empty.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    Application,
    ApplicationStatusChange,
    JobOffer,
    User,
    UserPreferredEmploymentType,
    UserPreferredLocation,
    UserProfile,
)
from app.models.enums import ApplicationStatus, EmploymentType, ExperienceLevel, SourceKind
from app.schemas.user import UserRegister
from app.scripts.seed import seed_offers
from app.services.auth import register_user
from app.services.technology import get_or_create_technologies

DEMO_EMAIL = 'demo@jobradar.dev'
DEMO_PASSWORD = 'demo12345'

SAVED = ApplicationStatus.SAVED
APPLIED = ApplicationStatus.APPLIED
SCREENING = ApplicationStatus.SCREENING
INTERVIEW = ApplicationStatus.INTERVIEW
OFFER = ApplicationStatus.OFFER
ACCEPTED = ApplicationStatus.ACCEPTED
REJECTED = ApplicationStatus.REJECTED
DECLINED = ApplicationStatus.DECLINED

SKILLS = [
    'Python',
    'FastAPI',
    'Django',
    'SQL',
    'PostgreSQL',
    'Docker',
    'Git',
    'REST API',
    'pytest',
    'React',
    'TypeScript',
]


@dataclass
class DemoApplication:
    """One application: the offer (title and company from the seed file) and its history.

    `steps` are (status, days ago), oldest first; the last one is the current status.
    `interview_in_days` is negative for an interview that already happened.
    """

    title: str
    company: str
    steps: list[tuple[ApplicationStatus, int]]
    notes: str | None = None
    interview_in_days: int | None = None
    interview_hour: int = 10


APPLICATIONS = [
    DemoApplication(
        'Junior Python Developer',
        'Brightfold',
        [(SAVED, 41), (APPLIED, 40), (SCREENING, 34), (INTERVIEW, 27), (OFFER, 19), (ACCEPTED, 16)],
        notes='Accepted. Start date agreed for the beginning of next month.',
        interview_in_days=-25,
    ),
    DemoApplication(
        'Python Developer Intern',
        'Pixelgrove',
        [(APPLIED, 44), (SCREENING, 38), (INTERVIEW, 31), (OFFER, 24), (DECLINED, 21)],
        notes='Declined: took the Brightfold offer instead.',
        interview_in_days=-30,
    ),
    DemoApplication(
        'Vue.js Developer',
        'Odra Systems',
        [(APPLIED, 28), (SCREENING, 21), (INTERVIEW, 14), (OFFER, 5)],
        notes='Offer: B2B, answer expected this week. Compare with the other processes first.',
        interview_in_days=-13,
    ),
    DemoApplication(
        'Junior Backend Developer (Python)',
        'Lumenkraft',
        [(SAVED, 30), (APPLIED, 29), (SCREENING, 22), (INTERVIEW, 12)],
        notes='Technical interview with the team lead. Revise FastAPI, SQL joins and testing.',
        interview_in_days=2,
    ),
    DemoApplication(
        'Fullstack Developer (Python + React)',
        'Pixelgrove',
        [(SAVED, 25), (APPLIED, 24), (SCREENING, 17), (INTERVIEW, 9)],
        notes='Second stage: live coding in React.',
        interview_in_days=6,
        interview_hour=13,
    ),
    DemoApplication(
        'Python Backend Developer',
        'Kestrel Data',
        [(APPLIED, 35), (SCREENING, 27), (INTERVIEW, 20), (REJECTED, 14)],
        notes='Feedback: more experience with async Python and message queues needed.',
        interview_in_days=-18,
    ),
    DemoApplication(
        'Junior Fullstack Developer',
        'Lumenkraft',
        [(APPLIED, 20), (SCREENING, 13)],
        notes='Recruiter call went well, waiting for the next step.',
    ),
    DemoApplication('Junior QA Engineer', 'Vistula Cloud', [(APPLIED, 15), (SCREENING, 8)]),
    DemoApplication('Junior Data Analyst', 'Nordbyte', [(APPLIED, 33), (REJECTED, 28)]),
    DemoApplication('Junior ML Engineer', 'Amberline Logistics', [(APPLIED, 26), (REJECTED, 19)]),
    DemoApplication('Junior Java Developer', 'Copperleaf Health', [(APPLIED, 38), (REJECTED, 30)]),
    DemoApplication('Junior DevOps Engineer', 'Odra Systems', [(APPLIED, 18)]),
    DemoApplication('Go Developer', 'Brightfold', [(SAVED, 13), (APPLIED, 11)]),
    DemoApplication('AI Engineer (LLM applications)', 'Pixelgrove', [(SAVED, 8), (APPLIED, 6)]),
    DemoApplication('Junior Frontend Developer', 'Ferroway', [(APPLIED, 4)]),
    DemoApplication('Data Engineer', 'Vistula Cloud', [(APPLIED, 2)]),
    DemoApplication(
        'Machine Learning Engineer',
        'Tatra Analytics',
        [(SAVED, 12)],
        notes='Mid level, maybe in a year.',
    ),
    DemoApplication('DevOps Engineer', 'Kestrel Data', [(SAVED, 3)]),
    DemoApplication('Python Developer (part-time, students welcome)', 'Odra Systems', [(SAVED, 1)]),
]


@dataclass
class DemoPrivateOffer:
    """An offer the demo user added by hand (only they see it)."""

    title: str
    company: str
    url: str
    location: str
    level: ExperienceLevel
    employment_type: EmploymentType
    technologies: list[str]
    description: str
    deadline_in_days: int | None = None
    steps: list[tuple[ApplicationStatus, int]] = field(default_factory=list)  # empty: not tracked


PRIVATE_OFFERS = [
    DemoPrivateOffer(
        'Junior Python Developer',
        'Riverbend Software',
        'https://example.com/jobs/riverbend-junior-python',
        'Wrocław, PL',
        ExperienceLevel.JUNIOR,
        EmploymentType.FULL_TIME,
        ['Python', 'Django', 'PostgreSQL', 'Docker'],
        'Riverbend builds booking software for clinics. As a junior Python developer you will '
        'work on our Django backend with a mentor: new API endpoints, tests and small '
        'database changes.\n\nRequirements: Python, Django or another web framework, SQL '
        'basics, Git. Nice to have: Docker, PostgreSQL.\n\nWe offer: hybrid work in Wrocław, '
        'a training budget and a mentor for the first six months.',
        deadline_in_days=9,
        steps=[(SAVED, 2)],
    ),
    DemoPrivateOffer(
        'Backend Developer (FastAPI)',
        'Northwind Labs',
        'https://example.com/jobs/northwind-fastapi',
        'Remote',
        ExperienceLevel.JUNIOR,
        EmploymentType.B2B,
        ['Python', 'FastAPI', 'PostgreSQL', 'pytest'],
        'Northwind Labs is a small remote team building APIs for logistics companies. You '
        'will write FastAPI services, cover them with pytest and help with code reviews.'
        '\n\nRequirements: Python, FastAPI or Flask, REST APIs, SQL. Nice to have: pytest, '
        'Docker, English B2.\n\nB2B contract, fully remote, flexible hours.',
        deadline_in_days=16,
    ),
]


def at(now: datetime, days_ago: int, hour: int = 9) -> datetime:
    """A moment `days_ago` days before now, at the given hour (UTC), never in the future."""
    day = (now - timedelta(days=days_ago)).date()
    moment = datetime.combine(day, time(hour), tzinfo=UTC)
    return min(moment, now)


def delete_demo_user(db: Session) -> None:
    """Delete the demo account; the database deletes everything that is only theirs."""
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is not None:
        db.delete(user)
        db.commit()


def fill_profile(db: Session, user: User) -> None:
    user.profile = UserProfile(
        desired_position='Python developer', experience_level=ExperienceLevel.JUNIOR
    )
    user.preferred_locations = [
        UserPreferredLocation(location=place) for place in ('Wrocław', 'Remote')
    ]
    user.preferred_employment_types = [
        UserPreferredEmploymentType(employment_type=kind)
        for kind in (EmploymentType.FULL_TIME, EmploymentType.B2B)
    ]
    user.technologies = get_or_create_technologies(db, SKILLS)


def make_application(
    user: User,
    offer: JobOffer,
    steps: list[tuple[ApplicationStatus, int]],
    now: datetime,
    notes: str | None = None,
    interview_at: datetime | None = None,
) -> Application:
    """An application whose history is `steps`, with the dates the stats read set to match."""
    changes = [ApplicationStatusChange(status=s, changed_at=at(now, days)) for s, days in steps]
    applied = next((c.changed_at for c in changes if c.status != SAVED), None)
    return Application(
        user_id=user.id,
        job_offer=offer,
        status=steps[-1][0],
        notes=notes,
        applied_at=applied,
        interview_at=interview_at,
        created_at=changes[0].changed_at,
        updated_at=changes[-1].changed_at,
        status_changes=changes,
    )


def public_offer(db: Session, title: str, company: str) -> JobOffer:
    offer = db.scalar(
        select(JobOffer).where(
            JobOffer.owner_id.is_(None),
            JobOffer.title == title,
            JobOffer.company_name == company,
        )
    )
    if offer is None:
        raise LookupError(f'Seed offer not found: {title} at {company}. Run `just seed` first.')
    return offer


def end_of_day(now: datetime, in_days: int | None) -> datetime | None:
    if in_days is None:
        return None
    return datetime.combine((now + timedelta(days=in_days)).date(), time(23), tzinfo=UTC)


def interview_moment(now: datetime, item: DemoApplication) -> datetime | None:
    if item.interview_in_days is None:
        return None
    day = (now + timedelta(days=item.interview_in_days)).date()
    return datetime.combine(day, time(item.interview_hour), tzinfo=UTC)


def seed_demo(db: Session, now: datetime | None = None) -> User:
    """Create the demo account anew and return it."""
    now = now or datetime.now(UTC)
    has_public_offers = db.scalar(select(JobOffer.id).where(JobOffer.owner_id.is_(None)).limit(1))
    if has_public_offers is None:
        seed_offers(db)

    delete_demo_user(db)
    user = register_user(db, UserRegister(email=DEMO_EMAIL, password=DEMO_PASSWORD))
    user.created_at = at(now, 45, hour=8)
    fill_profile(db, user)

    for item in APPLICATIONS:
        offer = public_offer(db, item.title, item.company)
        db.add(
            make_application(user, offer, item.steps, now, item.notes, interview_moment(now, item))
        )

    for private in PRIVATE_OFFERS:
        offer = JobOffer(
            owner_id=user.id,
            title=private.title,
            company_name=private.company,
            source=SourceKind.MANUAL,
            url=private.url,
            location=private.location,
            experience_level=private.level,
            employment_type=private.employment_type,
            description=private.description,
            deadline=end_of_day(now, private.deadline_in_days),
            technologies=get_or_create_technologies(db, private.technologies),
            created_at=at(now, private.steps[0][1] if private.steps else 1),
        )
        db.add(offer)
        if private.steps:
            db.add(make_application(user, offer, private.steps, now))

    db.commit()
    return user


def main() -> None:
    with SessionLocal() as db:
        user = seed_demo(db)
        print(
            f'Demo account ready: {DEMO_EMAIL} / {DEMO_PASSWORD} '
            f'({len(APPLICATIONS) + 1} applications, {len(PRIVATE_OFFERS)} private offers, '
            f'user id {user.id})'
        )


if __name__ == '__main__':
    main()
