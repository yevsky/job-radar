"""An admin's on/off switches for search sources, on top of each user's own choice."""

from typing import Any

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_search_sources
from app.main import app
from app.models import SearchRun, SearchSourceSwitch
from app.schemas.job_offer import JobOfferImport
from app.search_sources.fake import FakeSearchSource
from tests.helpers import auth_header

ADMIN_URL = '/admin/search-sources'
FORM = {'position': 'Python developer'}


def result(path: str) -> JobOfferImport:
    return JobOfferImport.model_validate(
        {'title': 'Python Developer', 'company_name': 'Codesky', 'url': f'https://a.pl/{path}'}
    )


@pytest.fixture(autouse=True)
def two_sources(api: TestClient) -> None:
    """The server has two sources, 'tavily' and 'jsearch' (fakes)."""
    del api  # requested only for its cleanup of app.dependency_overrides
    sources = [
        FakeSearchSource(name='tavily', results=[result('t1')]),
        FakeSearchSource(name='jsearch', results=[result('j1')]),
    ]
    app.dependency_overrides[get_search_sources] = lambda: sources


def switch(api: TestClient, token: str, name: str, enabled: bool) -> Any:
    return api.put(f'{ADMIN_URL}/{name}', json={'enabled': enabled}, headers=auth_header(token))


def search(api: TestClient, token: str) -> Any:
    return api.post('/search', json=FORM, headers=auth_header(token))


def found_via(api: TestClient, token: str) -> list[str]:
    response = search(api, token)
    assert response.status_code == status.HTTP_200_OK, response.text
    return [r['found_via'] for r in response.json()['results']]


# the admin side


def test_every_source_starts_switched_on(api: TestClient, admin_token: str) -> None:
    body = api.get(ADMIN_URL, headers=auth_header(admin_token)).json()

    assert [(s['name'], s['enabled'], s['ok']) for s in body] == [
        ('tavily', True, None),  # no check asked, so no real API call
        ('jsearch', True, None),
    ]


def test_admin_switches_a_source_off(api: TestClient, admin_token: str) -> None:
    response = switch(api, admin_token, 'jsearch', False)

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['enabled'] is False
    assert response.json()['updated_at'] is not None
    listed = api.get(ADMIN_URL, headers=auth_header(admin_token)).json()
    assert {s['name']: s['enabled'] for s in listed} == {'tavily': True, 'jsearch': False}


def test_switch_remembers_who_flipped_it(api: TestClient, admin_token: str, db: Session) -> None:
    switch(api, admin_token, 'tavily', False)

    me = api.get('/auth/me', headers=auth_header(admin_token)).json()
    row = db.get(SearchSourceSwitch, 'tavily')
    assert row is not None
    assert row.updated_by_id == me['id']


def test_switching_an_unknown_source_returns_404(api: TestClient, admin_token: str) -> None:
    response = switch(api, admin_token, 'google', False)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_normal_user_cannot_flip_switches(api: TestClient, access_token: str) -> None:
    response = switch(api, access_token, 'jsearch', False)

    assert response.status_code == status.HTTP_403_FORBIDDEN


# what users get


def test_switched_off_source_is_left_out_of_every_search(
    api: TestClient, admin_token: str, access_token: str
) -> None:
    switch(api, admin_token, 'jsearch', False)

    assert found_via(api, access_token) == ['tavily']


def test_switching_it_on_again_brings_it_back(
    api: TestClient, admin_token: str, access_token: str
) -> None:
    switch(api, admin_token, 'jsearch', False)
    switch(api, admin_token, 'jsearch', True)

    assert found_via(api, access_token) == ['tavily', 'jsearch']


def test_user_sees_which_sources_are_switched_off(
    api: TestClient, admin_token: str, access_token: str
) -> None:
    switch(api, admin_token, 'tavily', False)

    body = api.get('/search/sources', headers=auth_header(access_token)).json()

    assert body['available'] == ['jsearch']
    assert body['turned_off'] == ['tavily']


def test_users_own_choice_is_kept_while_a_source_is_off(
    api: TestClient, admin_token: str, access_token: str
) -> None:
    """A user who chose only JSearch gets the other sources while JSearch is off, and only
    JSearch again once it is back on. Their saved choice never changes."""
    api.put('/search/sources', json={'sources': ['jsearch']}, headers=auth_header(access_token))
    switch(api, admin_token, 'jsearch', False)

    assert found_via(api, access_token) == ['tavily']
    chosen = api.get('/search/sources', headers=auth_header(access_token)).json()['chosen']
    assert chosen == ['jsearch']

    switch(api, admin_token, 'jsearch', True)
    assert found_via(api, access_token) == ['jsearch']


def test_user_cannot_choose_a_switched_off_source(
    api: TestClient, admin_token: str, access_token: str
) -> None:
    switch(api, admin_token, 'jsearch', False)

    response = api.put(
        '/search/sources', json={'sources': ['jsearch']}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_with_every_source_off_search_returns_503_and_costs_nothing(
    api: TestClient, admin_token: str, access_token: str, db: Session
) -> None:
    switch(api, admin_token, 'tavily', False)
    switch(api, admin_token, 'jsearch', False)

    response = search(api, access_token)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert db.query(SearchRun).count() == 0
