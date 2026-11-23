"""GET /admin/job-offers: the admin's overview of public offers."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Application
from app.models.enums import ApplicationStatus, SourceKind
from tests.helpers import auth_header, make_offer

URL = '/admin/job-offers'
NOW = datetime.now(UTC)


@pytest.fixture
def offers(db: Session, registered_user_id: int) -> None:
    """Three public offers (one hidden, one from a search) and one private offer."""
    db.add_all(
        [
            make_offer('https://e.com/1', title='Python Developer', created_at=NOW - timedelta(3)),
            make_offer(
                'https://e.com/2',
                company_name='Datafy',
                is_active=False,
                created_at=NOW - timedelta(2),
            ),
            make_offer('https://e.com/3', source=SourceKind.SEARCH, created_at=NOW - timedelta(1)),
            make_offer('https://e.com/private', owner_id=registered_user_id),
        ]
    )
    db.flush()


def get(api: TestClient, token: str, **params: Any) -> dict[str, Any]:
    response = api.get(URL, params=params, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, Any] = response.json()
    return body


def urls(body: dict[str, Any]) -> list[str]:
    return [item['url'] for item in body['items']]


@pytest.mark.usefixtures('offers')
def test_lists_public_offers_newest_first_with_hidden_ones(
    api: TestClient, admin_token: str
) -> None:
    body = get(api, admin_token)

    assert urls(body) == ['https://e.com/3', 'https://e.com/2', 'https://e.com/1']
    assert body['total'] == 3
    assert [item['is_active'] for item in body['items']] == [True, False, True]


@pytest.mark.usefixtures('offers')
def test_never_lists_private_offers(api: TestClient, admin_token: str) -> None:
    assert 'https://e.com/private' not in urls(get(api, admin_token))


@pytest.mark.usefixtures('offers')
@pytest.mark.parametrize(
    ('params', 'expected'),
    [
        ({'q': 'python'}, ['https://e.com/1']),
        ({'q': 'DATAFY'}, ['https://e.com/2']),
        ({'is_active': 'false'}, ['https://e.com/2']),
        ({'source': 'search'}, ['https://e.com/3']),
        ({'limit': 1, 'offset': 1}, ['https://e.com/2']),
    ],
)
def test_filters_and_pages(
    api: TestClient, admin_token: str, params: dict[str, Any], expected: list[str]
) -> None:
    assert urls(get(api, admin_token, **params)) == expected


def test_counts_the_users_who_track_an_offer(
    api: TestClient, admin_token: str, db: Session, registered_user_id: int
) -> None:
    offer = make_offer('https://e.com/1')
    db.add(offer)
    db.flush()
    db.add(
        Application(
            user_id=registered_user_id, job_offer_id=offer.id, status=ApplicationStatus.APPLIED
        )
    )
    db.flush()

    assert get(api, admin_token)['items'][0]['saved_by'] == 1


def test_normal_user_cannot_see_the_overview(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN
