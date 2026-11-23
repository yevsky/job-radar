import json
from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import JobOffer
from app.models.enums import SourceKind
from tests.helpers import auth_header

IMPORT_URL = '/admin/job-offers/import'


def offer_row(number: int, **overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        'title': f'Backend Developer {number}',
        'company_name': 'Codesky',
        'url': f'https://example.com/jobs/{number}',
        'technologies': ['Python'],
    }
    row.update(overrides)
    return row


def upload(api: TestClient, token: str, content: bytes, filename: str = 'offers.json') -> Any:
    files = {'file': (filename, content, 'application/json')}
    return api.post(IMPORT_URL, files=files, headers=auth_header(token))


def as_json(data: object) -> bytes:
    return json.dumps(data).encode()


def count_offers(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(JobOffer)) or 0


def test_import_without_token_returns_401(api: TestClient) -> None:
    response = api.post(IMPORT_URL, files={'file': ('offers.json', b'[]', 'application/json')})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_import_as_user_returns_403(api: TestClient, access_token: str, db: Session) -> None:
    response = upload(api, access_token, as_json([offer_row(1)]))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert count_offers(db) == 0


def test_admin_imports_valid_file(api: TestClient, admin_token: str) -> None:
    response = upload(api, admin_token, as_json([offer_row(1), offer_row(2)]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'created': 2, 'updated': 0, 'skipped': 0, 'errors': []}

    listed = api.get('/job-offers', headers=auth_header(admin_token)).json()
    assert listed['total'] == 2
    assert sorted(item['title'] for item in listed['items']) == [
        'Backend Developer 1',
        'Backend Developer 2',
    ]


def test_imported_offers_have_manual_source(api: TestClient, admin_token: str, db: Session) -> None:
    upload(api, admin_token, as_json([offer_row(1)]))

    assert db.scalars(select(JobOffer.source)).all() == [SourceKind.POSTED]


def test_uploading_same_file_twice_updates(api: TestClient, admin_token: str, db: Session) -> None:
    content = as_json([offer_row(1), offer_row(2)])
    upload(api, admin_token, content)

    response = upload(api, admin_token, content)

    assert response.json()['created'] == 0
    assert response.json()['updated'] == 2
    assert count_offers(db) == 2


def test_invalid_rows_are_reported_and_valid_rows_import(
    api: TestClient, admin_token: str, db: Session
) -> None:
    rows = [offer_row(1), offer_row(2, url='not a url'), offer_row(3)]

    response = upload(api, admin_token, as_json(rows))

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['created'] == 2
    assert [error['row'] for error in body['errors']] == [2]
    assert 'url' in body['errors'][0]['message']
    assert count_offers(db) == 2


def test_empty_list_imports_nothing(api: TestClient, admin_token: str) -> None:
    response = upload(api, admin_token, b'[]')

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}


@pytest.mark.parametrize(
    'content',
    [
        b'[{"title": "Backend"',  # cut off
        b'not json at all',
        b'',  # empty file
        b'\xff\xfe\x00',  # not UTF-8 text
    ],
    ids=['broken', 'text', 'empty', 'binary'],
)
def test_invalid_json_returns_400(
    api: TestClient, admin_token: str, db: Session, content: bytes
) -> None:
    response = upload(api, admin_token, content)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['detail'] == 'The file is not valid JSON.'
    assert count_offers(db) == 0


@pytest.mark.parametrize(
    'data',
    [offer_row(1), 'just a string', 42, [offer_row(1), 'not an object'], [[offer_row(1)]]],
    ids=['object', 'string', 'number', 'mixed-list', 'nested-list'],
)
def test_json_that_is_not_a_list_of_objects_returns_400(
    api: TestClient, admin_token: str, db: Session, data: object
) -> None:
    response = upload(api, admin_token, as_json(data))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()['detail'] == 'The file must contain a JSON list of objects.'
    assert count_offers(db) == 0


def test_file_over_1_mb_returns_413(api: TestClient, admin_token: str, db: Session) -> None:
    content = b'[' + b' ' * 1_000_000 + b']'  # valid JSON, just too big

    response = upload(api, admin_token, content)

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    assert count_offers(db) == 0


def test_file_with_exactly_500_rows_is_accepted(api: TestClient, admin_token: str) -> None:
    response = upload(api, admin_token, as_json([offer_row(n) for n in range(500)]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['created'] == 500


def test_file_with_more_than_500_rows_returns_422(
    api: TestClient, admin_token: str, db: Session
) -> None:
    response = upload(api, admin_token, as_json([offer_row(n) for n in range(501)]))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert count_offers(db) == 0


def test_request_without_file_returns_422(api: TestClient, admin_token: str) -> None:
    response = api.post(IMPORT_URL, headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
