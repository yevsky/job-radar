from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import JobOffer, Technology
from app.models.enums import SourceKind
from app.services.job_offer_import import import_offers
from tests.conftest import register_and_login
from tests.helpers import auth_header, make_offer

URL = '/job-offers'
LINK = 'https://example.com/jobs/1'


def offer_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        'title': 'Backend Developer',
        'company_name': 'Codesky',
        'url': LINK,
        'location': 'Wrocław',
        'employment_type': 'b2b',
        'experience_level': 'junior',
        'technologies': ['Python', 'FastAPI'],
    }
    body.update(overrides)
    return body


def count_offers(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(JobOffer)) or 0


@pytest.fixture
def other_token(api: TestClient) -> str:
    _, token = register_and_login(api, 'other@example.com')
    return token


@pytest.fixture
def public_offer(db: Session) -> JobOffer:
    """An offer found by search, visible to everyone."""
    offer = make_offer(LINK, title='Public title', source=SourceKind.SEARCH)
    db.add(offer)
    db.flush()
    return offer


def add(api: TestClient, token: str, **overrides: Any) -> dict[str, Any]:
    response = api.post(URL, json=offer_body(**overrides), headers=auth_header(token))
    assert response.status_code == status.HTTP_201_CREATED
    return dict(response.json())


# --- POST /job-offers -----------------------------------------------------------------


def test_create_without_token_returns_401(api: TestClient, db: Session) -> None:
    response = api.post(URL, json=offer_body())

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert count_offers(db) == 0


def test_user_adds_private_offer(
    api: TestClient, access_token: str, registered_user_id: int, db: Session
) -> None:
    body = add(api, access_token)

    assert body['title'] == 'Backend Developer'
    assert body['url'] == LINK
    assert body['source'] == SourceKind.MANUAL
    assert body['is_active'] is True
    assert body['is_private'] is True
    assert body['last_seen_at'] is not None
    assert body['technologies'] == ['FastAPI', 'Python']
    offer = db.get(JobOffer, body['id'])
    assert offer is not None
    assert offer.owner_id == registered_user_id


def test_owner_sees_private_offer_in_list_and_details(api: TestClient, access_token: str) -> None:
    created = add(api, access_token)

    listed = api.get(URL, headers=auth_header(access_token)).json()
    details = api.get(f'{URL}/{created["id"]}', headers=auth_header(access_token))

    assert [item['id'] for item in listed['items']] == [created['id']]
    assert details.status_code == status.HTTP_200_OK
    assert details.json() == created


def test_other_user_does_not_see_private_offer(
    api: TestClient, access_token: str, other_token: str
) -> None:
    created = add(api, access_token)

    listed = api.get(URL, headers=auth_header(other_token)).json()
    details = api.get(f'{URL}/{created["id"]}', headers=auth_header(other_token))

    assert listed['items'] == []
    assert listed['total'] == 0
    assert details.status_code == status.HTTP_404_NOT_FOUND
    assert details.json() == {'detail': 'Job offer not found'}


def test_url_is_stored_normalized(api: TestClient, access_token: str) -> None:
    body = add(api, access_token, url='https://WWW.Example.com/jobs/1/?utm_source=linkedin#apply')

    assert body['url'] == LINK


@pytest.mark.parametrize(
    'same_link',
    [LINK, 'https://www.example.com/jobs/1/', 'https://example.com/jobs/1?utm_source=newsletter'],
)
def test_same_link_twice_returns_own_offer_with_200(
    api: TestClient, access_token: str, db: Session, same_link: str
) -> None:
    first = add(api, access_token)

    response = api.post(
        URL, json=offer_body(url=same_link, title='Second try'), headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['id'] == first['id']
    assert response.json()['title'] == 'Backend Developer'
    assert count_offers(db) == 1


def test_known_public_link_returns_public_offer_unchanged(
    api: TestClient, access_token: str, db: Session, public_offer: JobOffer
) -> None:
    response = api.post(
        URL, json=offer_body(title='Changed by a user'), headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['id'] == public_offer.id
    assert body['title'] == 'Public title'
    assert body['source'] == SourceKind.SEARCH
    assert body['is_private'] is False
    assert count_offers(db) == 1


def test_two_users_get_their_own_copies_of_one_link(
    api: TestClient, access_token: str, other_token: str, db: Session
) -> None:
    mine = add(api, access_token, title='My notes')
    theirs = add(api, other_token, title='Their notes')

    assert mine['id'] != theirs['id']
    assert count_offers(db) == 2
    assert api.get(URL, headers=auth_header(access_token)).json()['items'][0]['title'] == 'My notes'


def test_list_mixes_public_and_own_offers(
    api: TestClient, access_token: str, other_token: str, public_offer: JobOffer
) -> None:
    mine = add(api, access_token, url='https://example.com/jobs/mine')
    add(api, other_token, url='https://example.com/jobs/theirs')

    listed = api.get(URL, headers=auth_header(access_token)).json()

    assert {item['id'] for item in listed['items']} == {public_offer.id, mine['id']}
    assert listed['total'] == 2


def test_only_required_fields_are_enough(api: TestClient, access_token: str) -> None:
    body = {'title': 'Tester', 'company_name': 'Codesky', 'url': 'https://example.com/jobs/9'}

    response = api.post(URL, json=body, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['location'] is None
    assert response.json()['technologies'] == []


@pytest.mark.parametrize(
    'changes',
    [
        {'title': None},
        {'title': '   '},
        {'company_name': None},
        {'url': 'not a url'},
        {'url': 'ftp://example.com/jobs/1'},
        {'employment_type': 'freelance'},
        {'title': 'x' * 201},
    ],
    ids=['no-title', 'blank-title', 'no-company', 'bad-url', 'ftp-url', 'bad-type', 'long-title'],
)
def test_invalid_offer_returns_422(
    api: TestClient, access_token: str, db: Session, changes: dict[str, Any]
) -> None:
    body = {key: value for key, value in offer_body(**changes).items() if value is not None}

    response = api.post(URL, json=body, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert count_offers(db) == 0


# --- import never touches private offers ----------------------------------------------


def test_import_creates_public_offer_next_to_private_copy(
    api: TestClient, access_token: str, db: Session
) -> None:
    private = add(api, access_token, title='My notes')

    report = import_offers(
        db, [{'title': 'Imported', 'company_name': 'Codesky', 'url': LINK}], SourceKind.MANUAL
    )

    assert report.created == 1
    assert report.updated == 0
    private_offer = db.get(JobOffer, private['id'])
    assert private_offer is not None
    assert private_offer.title == 'My notes'
    public = db.scalar(select(JobOffer).where(JobOffer.owner_id.is_(None)))
    assert public is not None
    assert public.title == 'Imported'


def test_after_import_the_public_offer_is_returned(
    api: TestClient, access_token: str, db: Session
) -> None:
    add(api, access_token, title='My notes')
    import_offers(
        db, [{'title': 'Imported', 'company_name': 'Codesky', 'url': LINK}], SourceKind.MANUAL
    )

    response = api.post(URL, json=offer_body(), headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['title'] == 'Imported'


# --- DELETE /job-offers/{id} ----------------------------------------------------------


def test_delete_without_token_returns_401(api: TestClient, public_offer: JobOffer) -> None:
    response = api.delete(f'{URL}/{public_offer.id}')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_owner_deletes_private_offer(api: TestClient, access_token: str, db: Session) -> None:
    db.add(Technology(name='Python'))
    db.flush()
    created = add(api, access_token, technologies=['Python'])

    response = api.delete(f'{URL}/{created["id"]}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b''
    details = api.get(f'{URL}/{created["id"]}', headers=auth_header(access_token))
    assert details.status_code == status.HTTP_404_NOT_FOUND
    assert db.scalar(select(Technology).where(Technology.name == 'Python')) is not None


def test_user_cannot_delete_public_offer(
    api: TestClient, access_token: str, db: Session, public_offer: JobOffer
) -> None:
    response = api.delete(f'{URL}/{public_offer.id}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {'detail': 'You can only delete offers you added yourself'}
    assert count_offers(db) == 1


def test_user_cannot_delete_someone_elses_offer(
    api: TestClient, access_token: str, other_token: str, db: Session
) -> None:
    created = add(api, other_token)

    response = api.delete(f'{URL}/{created["id"]}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert count_offers(db) == 1


def test_delete_unknown_offer_returns_404(api: TestClient, access_token: str) -> None:
    response = api.delete(f'{URL}/999999', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_twice_returns_404_the_second_time(api: TestClient, access_token: str) -> None:
    created = add(api, access_token)
    api.delete(f'{URL}/{created["id"]}', headers=auth_header(access_token))

    response = api.delete(f'{URL}/{created["id"]}', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_404_NOT_FOUND
