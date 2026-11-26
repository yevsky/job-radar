from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, JobOffer, User
from app.models.enums import ApplicationStatus, SourceKind
from app.scripts.seed_demo import APPLICATIONS, DEMO_EMAIL, DEMO_PASSWORD, PRIVATE_OFFERS, seed_demo
from app.services.application import stale, stats
from tests.helpers import auth_header

NOW = datetime(2026, 11, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def demo(db: Session) -> User:
    return seed_demo(db, now=NOW)


def login(api: TestClient) -> str:
    response = api.post('/auth/login', data={'username': DEMO_EMAIL, 'password': DEMO_PASSWORD})
    assert response.status_code == 200
    token: str = response.json()['access_token']
    return token


@pytest.mark.usefixtures('demo')
def test_loads_the_public_offers_when_the_board_is_empty(db: Session) -> None:
    public = db.scalar(
        select(func.count()).select_from(JobOffer).where(JobOffer.owner_id.is_(None))
    )

    assert public == 40


@pytest.mark.usefixtures('demo')
def test_the_demo_user_can_log_in_and_has_a_profile(api: TestClient) -> None:
    token = login(api)

    profile = api.get('/profile/me', headers=auth_header(token)).json()

    assert profile['desired_position'] == 'Python developer'
    assert profile['experience_level'] == 'junior'
    assert 'Remote' in profile['preferred_locations']
    assert 'FastAPI' in profile['skills']


def test_creates_every_application_and_private_offer(db: Session, demo: User) -> None:
    applications = db.scalars(select(Application).where(Application.user_id == demo.id)).all()
    private = db.scalars(select(JobOffer).where(JobOffer.owner_id == demo.id)).all()

    tracked_private = sum(1 for offer in PRIVATE_OFFERS if offer.steps)
    assert len(applications) == len(APPLICATIONS) + tracked_private
    assert len(private) == len(PRIVATE_OFFERS)
    assert all(offer.source == SourceKind.MANUAL for offer in private)


def test_uses_every_status(db: Session, demo: User) -> None:
    statuses = set(db.scalars(select(Application.status).where(Application.user_id == demo.id)))

    assert statuses == set(ApplicationStatus)


def test_history_matches_the_current_status_and_is_in_the_past(db: Session, demo: User) -> None:
    applications = db.scalars(select(Application).where(Application.user_id == demo.id)).all()

    for application in applications:
        assert application.status_changes[-1].status == application.status
        assert all(change.changed_at <= NOW for change in application.status_changes)
        if application.status != ApplicationStatus.SAVED:
            assert application.applied_at is not None


def test_dashboard_has_a_funnel_weeks_and_stale_applications(db: Session, demo: User) -> None:
    numbers = stats(db, demo.id, 'all', now=NOW)
    stuck = stale(db, demo.id, now=NOW)

    reached = {step.stage: step.reached for step in numbers.funnel}
    assert reached[ApplicationStatus.APPLIED] > reached[ApplicationStatus.INTERVIEW] > 0
    assert reached[ApplicationStatus.ACCEPTED] == 1
    assert len(numbers.weekly) >= 6
    assert numbers.replied > 0
    assert sum(len(stage.items) for stage in stuck) >= 3


@pytest.mark.usefixtures('demo')
def test_has_interviews_ahead_for_the_calendar(api: TestClient) -> None:
    token = login(api)

    events = api.get(
        '/applications/calendar',
        params={'from': '2026-11-26', 'to': '2026-12-20'},
        headers=auth_header(token),
    ).json()

    kinds = {event['kind'] for event in events}
    assert {'interview', 'deadline'} <= kinds


@pytest.mark.usefixtures('demo')
def test_running_it_again_replaces_the_demo_account(db: Session) -> None:
    again = seed_demo(db, now=NOW)

    users = db.scalars(select(User).where(User.email == DEMO_EMAIL)).all()
    applications = db.scalar(
        select(func.count()).select_from(Application).where(Application.user_id == again.id)
    )
    assert len(users) == 1
    assert applications == len(APPLICATIONS) + 1
