from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import JobOffer, Technology
from app.models.job_offer import job_offer_technologies
from tests.helpers import auth_header, make_offer

ADMIN_OFFERS = '/admin/job-offers'


@pytest.fixture
def offer(db: Session) -> JobOffer:
    offer = make_offer('https://example.com/jobs/1', technologies=[Technology(name='Python')])
    db.add(offer)
    db.flush()
    return offer


def listed_ids(api: TestClient, token: str) -> list[int]:
    body = api.get('/job-offers', headers=auth_header(token)).json()
    return [item['id'] for item in body['items']]


def count(db: Session, table: Any) -> int:
    return db.scalar(select(func.count()).select_from(table)) or 0


# --- PATCH /admin/job-offers/{id} ---


def test_patch_without_token_returns_401(api: TestClient, offer: JobOffer) -> None:
    response = api.patch(f'{ADMIN_OFFERS}/{offer.id}', json={'is_active': False})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_patch_as_user_returns_403(api: TestClient, access_token: str, offer: JobOffer) -> None:
    response = api.patch(
        f'{ADMIN_OFFERS}/{offer.id}', json={'is_active': False}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert offer.is_active is True


def test_admin_hides_offer(api: TestClient, admin_token: str, offer: JobOffer) -> None:
    response = api.patch(
        f'{ADMIN_OFFERS}/{offer.id}', json={'is_active': False}, headers=auth_header(admin_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['id'] == offer.id
    assert response.json()['is_active'] is False
    assert listed_ids(api, admin_token) == []


def test_hidden_offer_can_still_be_opened_by_id(
    api: TestClient, admin_token: str, offer: JobOffer
) -> None:
    api.patch(
        f'{ADMIN_OFFERS}/{offer.id}', json={'is_active': False}, headers=auth_header(admin_token)
    )

    response = api.get(f'/job-offers/{offer.id}', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['is_active'] is False


def test_admin_shows_hidden_offer_again(api: TestClient, admin_token: str, offer: JobOffer) -> None:
    headers = auth_header(admin_token)
    api.patch(f'{ADMIN_OFFERS}/{offer.id}', json={'is_active': False}, headers=headers)

    response = api.patch(f'{ADMIN_OFFERS}/{offer.id}', json={'is_active': True}, headers=headers)

    assert response.json()['is_active'] is True
    assert listed_ids(api, admin_token) == [offer.id]


def test_patch_unknown_offer_returns_404(api: TestClient, admin_token: str) -> None:
    response = api.patch(
        f'{ADMIN_OFFERS}/999999', json={'is_active': False}, headers=auth_header(admin_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()['detail'] == 'Job offer not found'


@pytest.mark.parametrize('body', [{}, {'is_active': 'maybe'}, {'is_active': None}])
def test_patch_with_invalid_body_returns_422(
    api: TestClient, admin_token: str, offer: JobOffer, body: dict[str, object]
) -> None:
    response = api.patch(f'{ADMIN_OFFERS}/{offer.id}', json=body, headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# --- DELETE /admin/job-offers/{id} ---


def test_delete_without_token_returns_401(api: TestClient, offer: JobOffer) -> None:
    response = api.delete(f'{ADMIN_OFFERS}/{offer.id}')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_delete_as_user_returns_403(
    api: TestClient, access_token: str, offer: JobOffer, db: Session
) -> None:
    response = api.delete(f'{ADMIN_OFFERS}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert count(db, JobOffer) == 1


def test_admin_deletes_offer(
    api: TestClient, admin_token: str, offer: JobOffer, db: Session
) -> None:
    offer_id = offer.id

    response = api.delete(f'{ADMIN_OFFERS}/{offer_id}', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b''
    assert count(db, JobOffer) == 0
    details = api.get(f'/job-offers/{offer_id}', headers=auth_header(admin_token))
    assert details.status_code == status.HTTP_404_NOT_FOUND


def test_delete_removes_technology_links_but_keeps_technologies(
    api: TestClient, admin_token: str, offer: JobOffer, db: Session
) -> None:
    api.delete(f'{ADMIN_OFFERS}/{offer.id}', headers=auth_header(admin_token))

    assert count(db, job_offer_technologies) == 0
    assert count(db, Technology) == 1


def test_delete_unknown_offer_returns_404(api: TestClient, admin_token: str) -> None:
    response = api.delete(f'{ADMIN_OFFERS}/999999', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_deleting_twice_returns_404_the_second_time(
    api: TestClient, admin_token: str, offer: JobOffer
) -> None:
    headers = auth_header(admin_token)
    api.delete(f'{ADMIN_OFFERS}/{offer.id}', headers=headers)

    response = api.delete(f'{ADMIN_OFFERS}/{offer.id}', headers=headers)

    assert response.status_code == status.HTTP_404_NOT_FOUND


# --- private offers are off limits ---


def test_admin_cannot_touch_a_private_offer(
    api: TestClient, admin_token: str, access_token: str, db: Session
) -> None:
    created = api.post(
        '/job-offers',
        json={'title': 'Mine', 'company_name': 'Codesky', 'url': 'https://example.com/mine'},
        headers=auth_header(access_token),
    ).json()

    hide = api.patch(
        f'{ADMIN_OFFERS}/{created["id"]}',
        json={'is_active': False},
        headers=auth_header(admin_token),
    )
    delete = api.delete(f'{ADMIN_OFFERS}/{created["id"]}', headers=auth_header(admin_token))

    assert hide.status_code == status.HTTP_404_NOT_FOUND
    assert delete.status_code == status.HTTP_404_NOT_FOUND
    assert count(db, JobOffer) == 1
