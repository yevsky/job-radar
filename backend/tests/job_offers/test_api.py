from datetime import UTC, datetime, timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobOffer, Technology
from app.models.enums import EmploymentType, ExperienceLevel
from tests.helpers import auth_header, make_offer

URL = '/job-offers'
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def add_offers(db: Session, count: int) -> list[JobOffer]:
    """Add `count` active offers; offer i is i hours older than offer 0 (offer 0 is newest)."""
    offers = [
        make_offer(
            url=f'https://example.com/jobs/{i}',
            title=f'Offer {i}',
            created_at=NOW - timedelta(hours=i),
        )
        for i in range(count)
    ]
    db.add_all(offers)
    db.flush()
    return offers


def titles(body: dict[str, object]) -> list[str]:
    items = body['items']
    assert isinstance(items, list)
    return [item['title'] for item in items]


def test_list_without_token_returns_401(api: TestClient) -> None:
    response = api.get(URL)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_with_no_offers_returns_empty_page(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'items': [], 'total': 0, 'limit': 20, 'offset': 0}


def test_list_returns_offer_fields_and_sorted_technology_names(
    api: TestClient, access_token: str, db: Session
) -> None:
    offer = make_offer(
        title='Python Developer',
        company_name='Codesky',
        location='Wrocław',
        employment_type=EmploymentType.B2B,
        experience_level=ExperienceLevel.JUNIOR,
        deadline=datetime(2026, 12, 31, tzinfo=UTC),
        technologies=[Technology(name='Python'), Technology(name='Docker')],
    )
    db.add(offer)
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['total'] == 1
    item = body['items'][0]
    assert item['id'] == offer.id
    assert item['title'] == 'Python Developer'
    assert item['company_name'] == 'Codesky'
    assert item['location'] == 'Wrocław'
    assert item['employment_type'] == 'b2b'
    assert item['experience_level'] == 'junior'
    assert item['deadline'].startswith('2026-12-31')
    assert item['technologies'] == ['Docker', 'Python']


def test_list_shows_newest_offers_first(api: TestClient, access_token: str, db: Session) -> None:
    oldest = make_offer(url='https://example.com/old', title='Old', created_at=NOW)
    newest = make_offer(
        url='https://example.com/new', title='New', created_at=NOW + timedelta(days=1)
    )
    db.add_all([oldest, newest])
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    assert titles(response.json()) == ['New', 'Old']


def test_offers_with_same_created_at_are_ordered_by_id(
    api: TestClient, access_token: str, db: Session
) -> None:
    first = make_offer(url='https://example.com/a', title='First', created_at=NOW)
    second = make_offer(url='https://example.com/b', title='Second', created_at=NOW)
    db.add(first)
    db.flush()
    db.add(second)
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    assert titles(response.json()) == ['Second', 'First']


def test_inactive_offers_are_not_listed_or_counted(
    api: TestClient, access_token: str, db: Session
) -> None:
    db.add_all(
        [
            make_offer(url='https://example.com/active', title='Active'),
            make_offer(url='https://example.com/closed', title='Closed', is_active=False),
        ]
    )
    db.flush()

    response = api.get(URL, headers=auth_header(access_token))

    body = response.json()
    assert titles(body) == ['Active']
    assert body['total'] == 1


def test_limit_returns_first_page_and_total_counts_all(
    api: TestClient, access_token: str, db: Session
) -> None:
    add_offers(db, 3)

    response = api.get(URL, params={'limit': 2}, headers=auth_header(access_token))

    body = response.json()
    assert titles(body) == ['Offer 0', 'Offer 1']
    assert body['total'] == 3
    assert body['limit'] == 2
    assert body['offset'] == 0


def test_offset_returns_next_page(api: TestClient, access_token: str, db: Session) -> None:
    add_offers(db, 3)

    response = api.get(URL, params={'limit': 2, 'offset': 2}, headers=auth_header(access_token))

    body = response.json()
    assert titles(body) == ['Offer 2']
    assert body['total'] == 3
    assert body['offset'] == 2


def test_offset_past_the_end_returns_empty_items(
    api: TestClient, access_token: str, db: Session
) -> None:
    add_offers(db, 2)

    response = api.get(URL, params={'offset': 10}, headers=auth_header(access_token))

    body = response.json()
    assert body['items'] == []
    assert body['total'] == 2


@pytest.mark.parametrize(
    'params',
    [
        {'limit': 0},
        {'limit': 101},
        {'offset': -1},
        {'limit': 'abc'},
    ],
)
def test_invalid_pagination_returns_422(
    api: TestClient, access_token: str, params: dict[str, int | str]
) -> None:
    response = api.get(URL, params=params, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_limit_100_is_allowed(api: TestClient, access_token: str) -> None:
    response = api.get(URL, params={'limit': 100}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
