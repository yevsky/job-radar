from typing import Any

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApplicationStatusChange, JobOffer
from tests.helpers import auth_header, make_offer

URL = '/applications'


def create(api: TestClient, token: str, **body: Any) -> Any:
    return api.post(URL, json=body, headers=auth_header(token))


def test_list_without_token_returns_401(api: TestClient) -> None:
    assert api.get(URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_list_starts_empty(api: TestClient, access_token: str) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []


def test_create_returns_201_with_the_offer(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    response = create(api, access_token, job_offer_id=offer.id, notes='Sent via the site')

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['status'] == 'applied'
    assert body['job_offer']['id'] == offer.id
    assert body['job_offer']['title'] == 'Python Developer'
    assert body['notes'] == 'Sent via the site'
    assert body['applied_at'] is not None
    assert body['interview_at'] is None


def test_create_saved_has_no_applied_date(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    body = create(api, access_token, job_offer_id=offer.id, status='saved').json()

    assert body['status'] == 'saved'
    assert body['applied_at'] is None


def test_create_twice_returns_the_same_application_with_200(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    first = create(api, access_token, job_offer_id=offer.id).json()

    response = create(api, access_token, job_offer_id=offer.id, status='interview')

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['id'] == first['id']
    assert response.json()['status'] == 'applied'


def test_create_for_missing_offer_returns_404(api: TestClient, access_token: str) -> None:
    response = create(api, access_token, job_offer_id=999_999)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_for_someone_elses_private_offer_returns_404(
    api: TestClient, access_token: str, other_token: str
) -> None:
    private = api.post(
        '/job-offers',
        json={'title': 'Secret', 'company_name': 'X', 'url': 'https://example.com/private'},
        headers=auth_header(other_token),
    ).json()

    response = create(api, access_token, job_offer_id=private['id'])

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_create_with_unknown_status_returns_422(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    response = create(api, access_token, job_offer_id=offer.id, status='ghosted')

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_list_shows_only_my_applications(
    api: TestClient, access_token: str, other_token: str, offer: JobOffer, second_offer: JobOffer
) -> None:
    create(api, access_token, job_offer_id=offer.id)
    create(api, other_token, job_offer_id=second_offer.id)

    body = api.get(URL, headers=auth_header(access_token)).json()

    assert [a['job_offer']['id'] for a in body] == [offer.id]


def test_list_filters_by_status(
    api: TestClient, access_token: str, offer: JobOffer, second_offer: JobOffer
) -> None:
    create(api, access_token, job_offer_id=offer.id, status='saved')
    create(api, access_token, job_offer_id=second_offer.id)

    body = api.get(URL, params={'status': 'saved'}, headers=auth_header(access_token)).json()

    assert [a['job_offer']['id'] for a in body] == [offer.id]


def test_patch_status_writes_history(
    api: TestClient, access_token: str, offer: JobOffer, db: Session
) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id).json()['id']

    response = api.patch(
        f'{URL}/{app_id}', json={'status': 'screening'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['status'] == 'screening'
    statuses = db.scalars(
        select(ApplicationStatusChange.status).where(
            ApplicationStatusChange.application_id == app_id
        )
    ).all()
    assert statuses == ['applied', 'screening']


def test_patch_same_status_adds_no_history(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id).json()['id']

    api.patch(f'{URL}/{app_id}', json={'status': 'applied'}, headers=auth_header(access_token))

    history = api.get(f'{URL}/{app_id}/history', headers=auth_header(access_token)).json()
    assert [h['status'] for h in history] == ['applied']


def test_patch_saved_to_applied_sets_applied_date(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id, status='saved').json()['id']

    body = api.patch(
        f'{URL}/{app_id}', json={'status': 'applied'}, headers=auth_header(access_token)
    ).json()

    assert body['status'] == 'applied'
    assert body['applied_at'] is not None


def test_patch_changes_only_sent_fields(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id, notes='keep me').json()['id']

    body = api.patch(
        f'{URL}/{app_id}',
        json={'interview_at': '2026-12-01T14:30:00Z', 'resume_id': 3},
        headers=auth_header(access_token),
    ).json()

    assert body['notes'] == 'keep me'
    assert body['interview_at'].startswith('2026-12-01T14:30:00')
    assert body['resume_id'] == 3


def test_patch_null_clears_a_field(api: TestClient, access_token: str, offer: JobOffer) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id, notes='old').json()['id']

    body = api.patch(
        f'{URL}/{app_id}', json={'notes': None}, headers=auth_header(access_token)
    ).json()

    assert body['notes'] is None


def test_patch_someone_elses_application_returns_404(
    api: TestClient, access_token: str, other_token: str, offer: JobOffer
) -> None:
    app_id = create(api, other_token, job_offer_id=offer.id).json()['id']

    response = api.patch(
        f'{URL}/{app_id}', json={'status': 'offer'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_history_is_oldest_first(api: TestClient, access_token: str, offer: JobOffer) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id, status='saved').json()['id']
    for new_status in ('applied', 'interview', 'rejected'):
        api.patch(f'{URL}/{app_id}', json={'status': new_status}, headers=auth_header(access_token))

    history = api.get(f'{URL}/{app_id}/history', headers=auth_header(access_token)).json()

    assert [h['status'] for h in history] == ['saved', 'applied', 'interview', 'rejected']


def test_history_of_missing_application_returns_404(api: TestClient, access_token: str) -> None:
    response = api.get(f'{URL}/999999/history', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_returns_204_and_removes_it(
    api: TestClient, access_token: str, offer: JobOffer
) -> None:
    app_id = create(api, access_token, job_offer_id=offer.id).json()['id']

    response = api.delete(f'{URL}/{app_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert api.get(URL, headers=auth_header(access_token)).json() == []


def test_delete_someone_elses_application_returns_404(
    api: TestClient, access_token: str, other_token: str, offer: JobOffer
) -> None:
    app_id = create(api, other_token, job_offer_id=offer.id).json()['id']

    response = api.delete(f'{URL}/{app_id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_deleting_the_offer_deletes_its_applications(
    api: TestClient, access_token: str, db: Session
) -> None:
    offer = make_offer('https://example.com/jobs/gone')
    db.add(offer)
    db.flush()
    create(api, access_token, job_offer_id=offer.id)

    db.delete(offer)
    db.flush()

    assert api.get(URL, headers=auth_header(access_token)).json() == []
