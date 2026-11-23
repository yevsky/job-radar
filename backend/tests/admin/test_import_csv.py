"""POST /admin/job-offers/import with a CSV file, and the CSV reader itself."""

from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.services.job_offer_import import ImportFileError, parse_csv_rows, parse_rows
from tests.helpers import auth_header

IMPORT_URL = '/admin/job-offers/import'

CSV = (
    'title,company_name,url,location,experience_level,technologies\n'
    'Backend Developer,Codesky,https://example.com/jobs/1,Wrocław,junior,"Python, FastAPI"\n'
    'Data Engineer,Datafy,https://example.com/jobs/2,,,\n'
)


def upload_csv(api: TestClient, token: str, content: str, filename: str = 'offers.csv') -> Any:
    files = {'file': (filename, content.encode(), 'text/csv')}
    return api.post(IMPORT_URL, files=files, headers=auth_header(token))


def test_admin_imports_a_csv_file(api: TestClient, admin_token: str) -> None:
    response = upload_csv(api, admin_token, CSV)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {'created': 2, 'updated': 0, 'skipped': 0, 'errors': []}
    items = api.get('/admin/job-offers', headers=auth_header(admin_token)).json()['items']
    by_title = {item['title']: item for item in items}
    assert by_title['Backend Developer']['technologies'] == ['FastAPI', 'Python']
    assert by_title['Backend Developer']['experience_level'] == 'junior'
    assert by_title['Data Engineer']['location'] is None


def test_csv_rows_with_errors_are_reported_by_line(api: TestClient, admin_token: str) -> None:
    content = CSV + 'No company,,https://example.com/jobs/3\n'

    body = upload_csv(api, admin_token, content).json()

    assert body['created'] == 2
    assert [error['row'] for error in body['errors']] == [3]
    assert 'company_name' in body['errors'][0]['message']


def test_csv_without_required_columns_returns_400(api: TestClient, admin_token: str) -> None:
    response = upload_csv(api, admin_token, 'title,url\nDev,https://example.com/1\n')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'company_name' in response.json()['detail']


def test_reimporting_a_csv_updates_the_offers(api: TestClient, admin_token: str) -> None:
    upload_csv(api, admin_token, CSV)

    body = upload_csv(api, admin_token, CSV).json()

    assert (body['created'], body['updated']) == (0, 2)


# the reader on its own


def test_semicolon_separated_file_from_excel_with_a_bom() -> None:
    content = '﻿title;company_name;url;technologies\nDev;Acme;https://e.com/1;Python,Go\n'

    rows = parse_csv_rows(content.encode())

    assert rows == [
        {
            'title': 'Dev',
            'company_name': 'Acme',
            'url': 'https://e.com/1',
            'technologies': ['Python', 'Go'],
        }
    ]


def test_header_names_ignore_case_and_spaces() -> None:
    rows = parse_csv_rows(b' Title , Company_Name ,URL\nDev,Acme,https://e.com/1\n')

    assert rows == [{'title': 'Dev', 'company_name': 'Acme', 'url': 'https://e.com/1'}]


def test_blank_lines_are_left_out() -> None:
    rows = parse_csv_rows(b'title,company_name,url\n\nDev,Acme,https://e.com/1\n,,\n')

    assert len(rows) == 1


def test_csv_that_is_not_utf8_is_refused() -> None:
    with pytest.raises(ImportFileError, match='UTF-8'):
        parse_csv_rows('title,company_name,url\nDev,Łódź,x\n'.encode('cp1250'))


@pytest.mark.parametrize(
    ('filename', 'content', 'expected_title'),
    [
        ('offers.json', b'[{"title": "A"}]', 'A'),
        ('offers.csv', b'title,company_name,url\nB,c,d\n', 'B'),
        ('offers.txt', b'  [{"title": "C"}]', 'C'),  # unknown extension: JSON starts with [
        (None, b'title,company_name,url\nD,c,d\n', 'D'),
    ],
)
def test_file_type_comes_from_the_name_or_the_first_character(
    filename: str | None, content: bytes, expected_title: str
) -> None:
    assert parse_rows(filename, content)[0]['title'] == expected_title
