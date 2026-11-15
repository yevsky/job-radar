from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import SourceKind
from tests.helpers import auth_header, make_offer

URL = '/job-offers'
TEXT = 'We build booking software.\n\nIn this role you will design REST APIs.'


def test_details_return_description(api: TestClient, access_token: str, db: Session) -> None:
    offer = make_offer(source=SourceKind.POSTED, description=TEXT)
    db.add(offer)
    db.flush()

    response = api.get(f'{URL}/{offer.id}', headers=auth_header(access_token))

    assert response.json()['description'] == TEXT
    assert response.json()['source'] == SourceKind.POSTED


def test_list_does_not_return_description(api: TestClient, access_token: str, db: Session) -> None:
    db.add(make_offer(source=SourceKind.POSTED, description=TEXT))
    db.flush()

    body = api.get(URL, headers=auth_header(access_token)).json()

    assert len(body['items']) == 1
    assert 'description' not in body['items'][0]


def test_user_can_save_offer_with_description(api: TestClient, access_token: str) -> None:
    response = api.post(
        URL,
        json={
            'title': 'Tester',
            'company_name': 'Codesky',
            'url': 'https://example.com/jobs/9',
            'description': f'  {TEXT}  ',
        },
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['description'] == TEXT


def test_too_long_description_returns_422(api: TestClient, access_token: str) -> None:
    response = api.post(
        URL,
        json={
            'title': 'Tester',
            'company_name': 'Codesky',
            'url': 'https://example.com/jobs/9',
            'description': 'x' * 20_001,
        },
        headers=auth_header(access_token),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
