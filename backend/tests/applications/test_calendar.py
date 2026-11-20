from datetime import UTC, datetime

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import ApplicationStatus as S
from tests.applications.history import track
from tests.helpers import auth_header

URL = '/applications/calendar'


def day(d: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2026, 11, d, hour, minute, tzinfo=UTC)


def events(api: TestClient, token: str, start: str, end: str) -> list[tuple[str, str, str | None]]:
    response = api.get(URL, params={'from': start, 'to': end}, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK
    return [(e['date'], e['kind'], e['status']) for e in response.json()]


def test_applied_status_changes_and_interview(
    api: TestClient,
    access_token: str,
    registered_user_id: int,
    offer: JobOffer,
    db: Session,
) -> None:
    track(
        db,
        registered_user_id,
        offer,
        [(S.SAVED, day(1)), (S.APPLIED, day(2)), (S.SCREENING, day(5)), (S.INTERVIEW, day(8))],
        interview_at=day(12, 14, 30),
    )

    found = events(api, access_token, '2026-11-01', '2026-11-30')

    # saved isn't an event; the interview shows once, on its own date
    assert found == [
        ('2026-11-02', 'applied', 'applied'),
        ('2026-11-05', 'status_change', 'screening'),
        ('2026-11-12', 'interview', 'interview'),
    ]


def test_interview_has_a_time(
    api: TestClient, access_token: str, registered_user_id: int, offer: JobOffer, db: Session
) -> None:
    track(db, registered_user_id, offer, [(S.APPLIED, day(2))], interview_at=day(12, 14, 30))

    response = api.get(
        URL, params={'from': '2026-11-12', 'to': '2026-11-12'}, headers=auth_header(access_token)
    )

    [event] = response.json()
    assert event['time'] == '14:30'
    assert event['title'] == 'Python Developer'
    assert event['company_name'] == 'Codesky'


def test_deadline_of_open_application(
    api: TestClient, access_token: str, registered_user_id: int, db: Session, offer: JobOffer
) -> None:
    offer.deadline = day(20)
    track(db, registered_user_id, offer, [(S.SAVED, day(1))])

    assert events(api, access_token, '2026-11-15', '2026-11-25') == [
        ('2026-11-20', 'deadline', None)
    ]


def test_no_deadline_after_rejection(
    api: TestClient, access_token: str, registered_user_id: int, db: Session, offer: JobOffer
) -> None:
    offer.deadline = day(20)
    track(db, registered_user_id, offer, [(S.APPLIED, day(1)), (S.REJECTED, day(3))])

    assert events(api, access_token, '2026-11-15', '2026-11-25') == []


def test_only_events_inside_the_range(
    api: TestClient, access_token: str, registered_user_id: int, offer: JobOffer, db: Session
) -> None:
    track(db, registered_user_id, offer, [(S.APPLIED, day(2)), (S.SCREENING, day(20))])

    assert events(api, access_token, '2026-11-10', '2026-11-30') == [
        ('2026-11-20', 'status_change', 'screening')
    ]


def test_other_users_events_are_hidden(
    api: TestClient, access_token: str, other_token: str, offer: JobOffer
) -> None:
    api.post('/applications', json={'job_offer_id': offer.id}, headers=auth_header(other_token))
    today = datetime.now(UTC).date().isoformat()

    assert events(api, access_token, today, today) == []


def test_from_after_to_returns_422(api: TestClient, access_token: str) -> None:
    response = api.get(
        URL, params={'from': '2026-11-10', 'to': '2026-11-01'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_range_longer_than_92_days_returns_422(api: TestClient, access_token: str) -> None:
    response = api.get(
        URL, params={'from': '2026-01-01', 'to': '2026-12-31'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_missing_dates_return_422(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
