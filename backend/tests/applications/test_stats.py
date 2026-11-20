from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import ApplicationStatus as S
from app.services.application import stats
from tests.applications.history import track
from tests.helpers import auth_header, make_offer

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)  # a Wednesday


def ago(days: int) -> datetime:
    return NOW - timedelta(days=days)


@pytest.fixture
def history(db: Session, registered_user_id: int) -> int:
    """Five applications with different fates, plus one offer that is only saved."""
    fates: list[list[tuple[S, datetime]]] = [
        [
            (S.APPLIED, ago(20)),
            (S.SCREENING, ago(15)),
            (S.INTERVIEW, ago(10)),
            (S.ACCEPTED, ago(2)),
        ],
        [(S.APPLIED, ago(20)), (S.SCREENING, ago(14)), (S.REJECTED, ago(12))],
        [(S.APPLIED, ago(9)), (S.REJECTED, ago(5))],
        [(S.SAVED, ago(12)), (S.APPLIED, ago(8)), (S.INTERVIEW, ago(3))],
        [(S.APPLIED, ago(60)), (S.OFFER, ago(40)), (S.DECLINED, ago(38))],
        [(S.SAVED, ago(1))],
    ]
    for i, steps in enumerate(fates):
        offer = make_offer(f'https://example.com/jobs/{i}')
        db.add(offer)
        db.flush()
        track(db, registered_user_id, offer, steps)
    return registered_user_id


def test_funnel_counts_how_far_applications_got(db: Session, history: int) -> None:
    result = stats(db, history, '30d', now=NOW)

    assert [(f.stage, f.reached) for f in result.funnel] == [
        ('applied', 4),
        ('screening', 3),  # the accepted one passed screening too
        ('interview', 2),
        ('offer', 1),
        ('accepted', 1),
    ]


def test_all_time_includes_old_applications(db: Session, history: int) -> None:
    result = stats(db, history, 'all', now=NOW)

    assert result.funnel[0].reached == 5
    assert result.funnel[3].reached == 2  # plus the offer declined 38 days ago


def test_outcomes_say_where_stopped_applications_are_now(db: Session, history: int) -> None:
    result = stats(db, history, '30d', now=NOW)

    assert {(o.stage, o.status, o.count) for o in result.outcomes} == {
        ('applied', 'rejected', 1),
        ('screening', 'rejected', 1),
        ('interview', 'interview', 1),
    }


def test_weekly_counts_saved_and_applied(db: Session, history: int) -> None:
    result = stats(db, history, '30d', now=NOW)

    weeks = {w.week_start: (w.saved, w.applied) for w in result.weekly}
    assert all(start.weekday() == 0 for start in weeks)
    assert weeks[date(2026, 11, 16)] == (1, 0)  # saved yesterday
    assert weeks[date(2026, 11, 9)] == (0, 2)  # applied 9 and 8 days ago
    assert weeks[date(2026, 11, 2)] == (1, 0)  # saved 12 days ago
    assert weeks[date(2026, 10, 26)] == (0, 2)  # applied 20 days ago, twice
    assert sum(applied for _, applied in weeks.values()) == 4


def test_empty_history(db: Session, registered_user_id: int) -> None:
    result = stats(db, registered_user_id, 'all', now=NOW)

    assert [f.reached for f in result.funnel] == [0, 0, 0, 0, 0]
    assert result.outcomes == []
    assert result.weekly == []


def test_stats_endpoint(api: TestClient, access_token: str, offer: JobOffer) -> None:
    api.post('/applications', json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    response = api.get(
        '/applications/stats', params={'range': '90d'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['range'] == '90d'
    assert body['funnel'][0] == {'stage': 'applied', 'reached': 1}
    assert body['weekly'][-1]['applied'] == 1


def test_stats_with_unknown_range_returns_422(api: TestClient, access_token: str) -> None:
    response = api.get(
        '/applications/stats', params={'range': '7d'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
