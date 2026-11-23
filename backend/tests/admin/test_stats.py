"""GET /admin/stats: the admin dashboard's numbers."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Application, Conversation, SearchRun, User
from app.models.enums import ApplicationStatus
from app.services.admin_stats import get_admin_stats
from tests.helpers import auth_header, make_offer

URL = '/admin/stats'


def stats(api: TestClient, token: str) -> dict[str, Any]:
    response = api.get(URL, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, Any] = response.json()
    return body


def test_counts_users_and_admins(
    api: TestClient, admin_token: str, registered_user_id: int
) -> None:
    del registered_user_id

    body = stats(api, admin_token)

    assert (body['users'], body['admins'], body['new_users_last_7_days']) == (2, 1, 2)


def test_counts_shown_hidden_and_private_offers(
    api: TestClient, admin_token: str, db: Session, registered_user_id: int
) -> None:
    db.add_all(
        [
            make_offer('https://e.com/1'),
            make_offer('https://e.com/2'),
            make_offer('https://e.com/3', is_active=False),
            make_offer('https://e.com/4', owner_id=registered_user_id),
        ]
    )
    db.flush()

    body = stats(api, admin_token)

    assert (body['public_offers'], body['hidden_offers'], body['private_offers']) == (2, 1, 1)


def test_counts_applications_by_status_with_zeros(
    api: TestClient, admin_token: str, db: Session, registered_user_id: int
) -> None:
    first, second = make_offer('https://e.com/1'), make_offer('https://e.com/2')
    db.add_all([first, second])
    db.flush()
    db.add_all(
        [
            Application(
                user_id=registered_user_id, job_offer_id=first.id, status=ApplicationStatus.SAVED
            ),
            Application(
                user_id=registered_user_id, job_offer_id=second.id, status=ApplicationStatus.APPLIED
            ),
            Conversation(user_id=registered_user_id),
        ]
    )
    db.flush()

    body = stats(api, admin_token)

    assert body['applications'] == 2
    assert body['applications_by_status']['saved'] == 1
    assert body['applications_by_status']['applied'] == 1
    assert body['applications_by_status']['offer'] == 0
    assert body['conversations'] == 1
    assert body['analyses'] == 0


def test_searches_per_day_cover_14_days_including_empty_ones(
    db: Session, registered_user_id: int
) -> None:
    now = datetime(2026, 11, 23, 12, tzinfo=UTC)
    db.add_all(
        [
            SearchRun(user_id=registered_user_id, result_count=3, created_at=now),
            SearchRun(user_id=registered_user_id, result_count=3, created_at=now),
            SearchRun(
                user_id=registered_user_id, result_count=1, created_at=now - timedelta(days=2)
            ),
            SearchRun(  # too old for the chart
                user_id=registered_user_id, result_count=1, created_at=now - timedelta(days=20)
            ),
        ]
    )
    db.flush()

    result = get_admin_stats(db, now)

    days = result.searches_by_day
    assert len(days) == 14
    assert days[0].day == date(2026, 11, 10)
    assert days[-1].day == date(2026, 11, 23)
    assert [d.count for d in days[-3:]] == [1, 0, 2]
    assert result.searches_today == 2
    assert result.searches_last_7_days == 3


def test_signups_are_grouped_by_week_starting_on_monday(db: Session) -> None:
    db.query(User).delete()
    now = datetime(2026, 11, 26, 12, tzinfo=UTC)  # a Thursday
    for created in [
        now,
        now - timedelta(days=3),
        now - timedelta(days=4),
        now - timedelta(days=30),
    ]:
        db.add(
            User(
                email=f'{created.isoformat()}@e.com',
                hashed_password='x',
                role_id=1,
                created_at=created,
            )
        )
    db.flush()

    weeks = get_admin_stats(db, now).signups_by_week

    assert len(weeks) == 8
    assert weeks[-1].day == date(2026, 11, 23)  # this Monday
    assert weeks[-1].count == 2  # Thursday and Monday
    assert weeks[-2].count == 1  # the Sunday before
    assert sum(week.count for week in weeks) == 4


def test_normal_user_cannot_see_stats(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN
