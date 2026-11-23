from fastapi import status
from fastapi.testclient import TestClient

from app.models import JobOffer
from tests.helpers import auth_header

URL = '/saved-jobs'


def test_save_returns_201_and_lists_it(api: TestClient, access_token: str, offer: JobOffer) -> None:
    response = api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['job_offer']['id'] == offer.id
    assert response.json()['status'] == 'saved'
    listed = api.get(URL, headers=auth_header(access_token)).json()
    assert [s['job_offer']['id'] for s in listed] == [offer.id]


def test_saved_offer_is_an_application_with_status_saved(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    applications = api.get('/applications', headers=auth_header(access_token)).json()

    assert [(a['job_offer']['id'], a['status']) for a in applications] == [(offer.id, 'saved')]


def test_save_twice_returns_200(api: TestClient, access_token: str, offer: JobOffer) -> None:
    api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    response = api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert len(api.get(URL, headers=auth_header(access_token)).json()) == 1


def test_save_missing_offer_returns_404(api: TestClient, access_token: str) -> None:
    response = api.post(URL, json={'job_offer_id': 999_999}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_applied_offer_is_not_listed_as_saved(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    app_id = api.post(
        URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token)
    ).json()['id']
    api.patch(
        f'/applications/{app_id}', json={'status': 'applied'}, headers=auth_header(access_token)
    )

    assert api.get(URL, headers=auth_header(access_token)).json() == []


def test_unsave_returns_204(api: TestClient, access_token: str, offer: JobOffer) -> None:
    api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    response = api.delete(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert api.get(URL, headers=auth_header(access_token)).json() == []
    assert api.get('/applications', headers=auth_header(access_token)).json() == []


def test_unsave_not_saved_returns_404(api: TestClient, access_token: str, offer: JobOffer) -> None:
    response = api.delete(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_unsave_keeps_an_application_already_sent(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    api.post('/applications', json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    response = api.delete(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert len(api.get('/applications', headers=auth_header(access_token)).json()) == 1


def test_saved_offers_are_per_user(
    api: TestClient, access_token: str, other_token: str, offer: JobOffer
) -> None:
    api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(other_token))

    assert api.get(URL, headers=auth_header(access_token)).json() == []


def test_save_of_an_offer_already_applied_to_says_its_status(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    """The Save button uses the status to show "Applied" instead of a Saved it can't undo."""
    api.post(
        '/applications',
        json={'job_offer_id': offer.id, 'status': 'interview'},
        headers=auth_header(access_token),
    )

    response = api.post(URL, json={'job_offer_id': offer.id}, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['status'] == 'interview'
