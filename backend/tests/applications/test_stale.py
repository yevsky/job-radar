from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import ApplicationStatus as S
from app.services.application import stale
from tests.applications.history import track
from tests.helpers import auth_header, make_offer

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


@pytest.fixture
def board(db: Session, registered_user_id: int) -> int:
    """Applications in every open status, some waiting longer than their rule allows."""
    rows: list[tuple[str, list[tuple[S, datetime]], datetime | None]] = [
        ('Old save', [(S.SAVED, ago(8))], None),
        ('New save', [(S.SAVED, ago(2))], None),
        ('Quiet company', [(S.SAVED, ago(20)), (S.APPLIED, ago(12))], None),
        ('Fresh application', [(S.APPLIED, ago(3))], None),
        ('Slow screening', [(S.APPLIED, ago(15)), (S.SCREENING, ago(10))], None),
        ('Interview ahead', [(S.APPLIED, ago(30)), (S.INTERVIEW, ago(20))], ago(-2)),
        ('No feedback', [(S.APPLIED, ago(30)), (S.INTERVIEW, ago(20))], ago(8)),
        ('Offer waiting', [(S.APPLIED, ago(30)), (S.OFFER, ago(4))], None),
        ('Closed', [(S.APPLIED, ago(40)), (S.REJECTED, ago(30))], None),
    ]
    for i, (title, steps, interview_at) in enumerate(rows):
        offer = make_offer(f'https://example.com/stale/{i}', title=title)
        db.add(offer)
        db.flush()
        track(db, registered_user_id, offer, steps, interview_at=interview_at)
    return registered_user_id


def test_one_row_per_open_status_in_board_order(db: Session, board: int) -> None:
    result = stale(db, board, now=NOW)

    assert [(s.stage, s.after_days, s.total) for s in result] == [
        ('saved', 7, 2),
        ('applied', 10, 2),
        ('screening', 10, 1),
        ('interview', 7, 2),
        ('offer', 3, 1),
    ]


def test_lists_only_what_waited_too_long(db: Session, board: int) -> None:
    result = {s.stage: [(i.title, i.days) for i in s.items] for s in stale(db, board, now=NOW)}

    assert result == {
        'saved': [('Old save', 8)],
        'applied': [('Quiet company', 12)],
        'screening': [('Slow screening', 10)],  # exactly on the limit counts
        'interview': [('No feedback', 8)],  # counted from the interview, not the status change
        'offer': [('Offer waiting', 4)],
    }


def test_interview_still_ahead_is_not_stale(db: Session, board: int) -> None:
    interview = next(s for s in stale(db, board, now=NOW) if s.stage == 'interview')

    assert 'Interview ahead' not in [i.title for i in interview.items]


def test_longest_wait_first(db: Session, registered_user_id: int) -> None:
    for i, days in enumerate([11, 25, 14]):
        offer = make_offer(f'https://example.com/wait/{i}', company_name=f'Company {i}')
        db.add(offer)
        db.flush()
        track(db, registered_user_id, offer, [(S.APPLIED, ago(days))])

    applied = next(s for s in stale(db, registered_user_id, now=NOW) if s.stage == 'applied')

    assert [i.days for i in applied.items] == [25, 14, 11]
    assert applied.items[0].company_name == 'Company 1'


def test_nothing_tracked_gives_empty_rows(db: Session, registered_user_id: int) -> None:
    result = stale(db, registered_user_id, now=NOW)

    assert all(s.total == 0 and s.items == [] for s in result)


def test_stale_endpoint(api: TestClient, access_token: str) -> None:
    response = api.get('/applications/stale', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert [s['stage'] for s in response.json()] == [
        'saved',
        'applied',
        'screening',
        'interview',
        'offer',
    ]


def test_stale_needs_login(api: TestClient) -> None:
    response = api.get('/applications/stale')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
