from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import SourceKind
from tests.conftest import register_and_login
from tests.helpers import auth_header, make_offer

URL = '/job-offers/mine'


@pytest.fixture
def public_offer(db: Session) -> JobOffer:
    """An offer posted on the site, for everyone."""
    offer = make_offer('https://example.com/jobs/public', title='Posted by admin')
    db.add(offer)
    db.flush()
    return offer


def mine(api: TestClient, token: str) -> list[dict[str, Any]]:
    response = api.get(URL, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK
    return list(response.json())


def add_private(api: TestClient, token: str, url: str, **fields: Any) -> dict[str, Any]:
    body = {'title': 'My offer', 'company_name': 'Codesky', 'url': url, **fields}
    response = api.post('/job-offers', json=body, headers=auth_header(token))
    assert response.status_code == status.HTTP_201_CREATED
    return dict(response.json())


def test_without_token_returns_401(api: TestClient) -> None:
    assert api.get(URL).status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.usefixtures('public_offer')
def test_public_offers_are_left_out_until_tracked(api: TestClient, access_token: str) -> None:
    assert mine(api, access_token) == []


def test_offer_added_by_hand_is_listed_without_an_application(
    api: TestClient, access_token: str
) -> None:
    added = add_private(api, access_token, 'https://example.com/jobs/mine')

    [item] = mine(api, access_token)

    assert item['id'] == added['id']
    assert item['source'] == SourceKind.MANUAL
    assert item['is_private'] is True
    assert item['application'] is None
    assert item['url'] == 'https://example.com/jobs/mine'


def test_saved_public_offer_is_listed_with_its_application(
    api: TestClient, access_token: str, public_offer: JobOffer
) -> None:
    saved = api.post(
        '/saved-jobs', json={'job_offer_id': public_offer.id}, headers=auth_header(access_token)
    ).json()

    [item] = mine(api, access_token)

    assert item['id'] == public_offer.id
    assert item['is_private'] is False
    assert item['application']['id'] == saved['id']
    assert item['application']['status'] == 'saved'


def test_public_offer_keeps_showing_after_applying(
    api: TestClient, access_token: str, public_offer: JobOffer
) -> None:
    api.post(
        '/applications',
        json={'job_offer_id': public_offer.id, 'status': 'applied'},
        headers=auth_header(access_token),
    )

    [item] = mine(api, access_token)

    assert item['application']['status'] == 'applied'


def test_hidden_offer_the_user_tracks_is_kept(
    api: TestClient, access_token: str, public_offer: JobOffer, db: Session
) -> None:
    api.post(
        '/saved-jobs', json={'job_offer_id': public_offer.id}, headers=auth_header(access_token)
    )
    public_offer.is_active = False
    db.flush()

    [item] = mine(api, access_token)

    assert item['is_active'] is False


def test_other_users_offers_and_applications_are_left_out(
    api: TestClient, access_token: str, public_offer: JobOffer
) -> None:
    _, other = register_and_login(api, 'other@example.com')
    add_private(api, other, 'https://example.com/jobs/theirs')
    api.post('/saved-jobs', json={'job_offer_id': public_offer.id}, headers=auth_header(other))

    assert mine(api, access_token) == []


def test_offer_from_search_keeps_where_it_was_found(
    api: TestClient, access_token: str, registered_user_id: int, db: Session
) -> None:
    offer = make_offer(
        'https://example.com/jobs/found',
        source=SourceKind.SEARCH,
        found_via='jsearch',
        owner_id=registered_user_id,
    )
    db.add(offer)
    db.flush()

    [item] = mine(api, access_token)

    assert item['source'] == SourceKind.SEARCH
    assert item['found_via'] == 'jsearch'


def test_newest_first(
    api: TestClient, access_token: str, registered_user_id: int, db: Session
) -> None:
    now = datetime.now(UTC)
    old = make_offer('https://example.com/jobs/old', title='Old', owner_id=registered_user_id)
    new = make_offer('https://example.com/jobs/new', title='New', owner_id=registered_user_id)
    old.created_at = now - timedelta(days=3)
    new.created_at = now
    db.add_all([old, new])
    db.flush()

    assert [item['title'] for item in mine(api, access_token)] == ['New', 'Old']
