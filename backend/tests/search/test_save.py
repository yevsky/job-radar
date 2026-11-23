from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import SourceKind
from tests.conftest import register_and_login
from tests.helpers import auth_header, make_offer

URL = '/search/results'
LINK = 'https://example.com/jobs/1'


def result_body(**overrides: Any) -> dict[str, Any]:
    """A search result as POST /search returns it, sent back to keep it."""
    body: dict[str, Any] = {
        'title': 'Python Developer',
        'company_name': 'Codesky',
        'url': LINK,
        'location': 'Remote',
        'technologies': ['Python', 'FastAPI'],
        'found_via': 'tavily',
    }
    body.update(overrides)
    return body


def save(api: TestClient, token: str, **overrides: Any) -> Any:
    return api.post(URL, json=result_body(**overrides), headers=auth_header(token))


def count_offers(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(JobOffer)) or 0


def listed_ids(api: TestClient, token: str) -> list[int]:
    """The user's own offers, as the My offers page lists them."""
    response = api.get('/job-offers/mine', headers=auth_header(token))
    return [item['id'] for item in response.json()]


@pytest.fixture
def other_token(api: TestClient) -> str:
    _, token = register_and_login(api, 'other@example.com')
    return token


def test_save_without_token_returns_401(api: TestClient, db: Session) -> None:
    response = api.post(URL, json=result_body())

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert count_offers(db) == 0


def test_saved_result_is_a_private_search_offer(
    api: TestClient, access_token: str, registered_user_id: int, db: Session
) -> None:
    response = save(api, access_token)

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['title'] == 'Python Developer'
    assert body['source'] == SourceKind.SEARCH
    assert body['found_via'] == 'tavily'
    assert body['is_private'] is True
    assert body['technologies'] == ['FastAPI', 'Python']
    offer = db.get(JobOffer, body['id'])
    assert offer is not None
    assert offer.owner_id == registered_user_id


def test_saved_result_shows_up_in_the_users_offers(api: TestClient, access_token: str) -> None:
    offer_id = save(api, access_token).json()['id']

    assert offer_id in listed_ids(api, access_token)
    details = api.get(f'/job-offers/{offer_id}', headers=auth_header(access_token))
    assert details.status_code == status.HTTP_200_OK
    assert details.json()['found_via'] == 'tavily'


def test_another_user_does_not_see_a_saved_result(
    api: TestClient, access_token: str, other_token: str
) -> None:
    offer_id = save(api, access_token).json()['id']

    assert offer_id not in listed_ids(api, other_token)
    details = api.get(f'/job-offers/{offer_id}', headers=auth_header(other_token))
    assert details.status_code == status.HTTP_404_NOT_FOUND


def test_saving_the_same_result_twice_returns_the_same_offer(
    api: TestClient, access_token: str, db: Session
) -> None:
    first = save(api, access_token)
    second = save(api, access_token, url='https://www.example.com/jobs/1/?utm_source=x')

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_200_OK
    assert second.json()['id'] == first.json()['id']
    assert count_offers(db) == 1


def test_two_users_saving_one_result_get_their_own_copies(
    api: TestClient, access_token: str, other_token: str, db: Session
) -> None:
    mine = save(api, access_token).json()['id']
    theirs = save(api, other_token).json()['id']

    assert mine != theirs
    assert count_offers(db) == 2


def test_result_already_public_returns_the_public_offer(
    api: TestClient, access_token: str, db: Session
) -> None:
    public = make_offer(LINK, title='Public title', source=SourceKind.POSTED)
    db.add(public)
    db.flush()

    response = save(api, access_token)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['id'] == public.id
    assert body['title'] == 'Public title'
    assert body['is_private'] is False
    assert body['found_via'] is None
    assert count_offers(db) == 1


def test_result_the_user_already_added_by_hand_is_not_changed(
    api: TestClient, access_token: str, db: Session
) -> None:
    added = api.post(
        '/job-offers', json=result_body(found_via=None), headers=auth_header(access_token)
    ).json()

    response = save(api, access_token)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['id'] == added['id']
    assert response.json()['source'] == SourceKind.MANUAL
    assert count_offers(db) == 1


def test_offer_added_by_hand_is_still_manual(api: TestClient, access_token: str) -> None:
    body = {key: value for key, value in result_body().items() if key != 'found_via'}

    response = api.post('/job-offers', json=body, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['source'] == SourceKind.MANUAL
    assert response.json()['found_via'] is None


def test_user_can_delete_a_saved_result(api: TestClient, access_token: str, db: Session) -> None:
    offer_id = save(api, access_token).json()['id']

    response = api.delete(f'/job-offers/{offer_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert count_offers(db) == 0


@pytest.mark.parametrize('found_via', [None, '', 'x' * 51])
def test_found_via_is_required_and_short(
    api: TestClient, access_token: str, db: Session, found_via: str | None
) -> None:
    response = save(api, access_token, found_via=found_via)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert count_offers(db) == 0


def test_saving_a_result_does_not_use_a_search(api: TestClient, access_token: str) -> None:
    save(api, access_token)

    usage = api.get('/search/usage', headers=auth_header(access_token)).json()
    assert usage['used_today'] == 0
