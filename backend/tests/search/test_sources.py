import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.dependencies import get_search_sources
from app.main import app
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import SourceFeature
from app.search_sources.fake import FakeSearchSource
from tests.conftest import register_and_login
from tests.helpers import auth_header

URL = '/search/sources'
FORM = {'position': 'Python developer'}


def result(path: str) -> JobOfferImport:
    return JobOfferImport.model_validate(
        {'title': 'Python Developer', 'company_name': 'Codesky', 'url': f'https://a.pl/{path}'}
    )


@pytest.fixture(autouse=True)
def two_sources(api: TestClient) -> None:
    """Every test here runs with two enabled sources, 'tavily' and 'jsearch' (fakes)."""
    del api  # requested only for its cleanup of app.dependency_overrides
    sources = [
        FakeSearchSource(name='tavily', results=[result('t1')]),
        FakeSearchSource(name='jsearch', results=[result('j1')]),
    ]
    app.dependency_overrides[get_search_sources] = lambda: sources


def choose(api: TestClient, token: str, sources: object) -> tuple[int, dict[str, object]]:
    response = api.put(URL, json={'sources': sources}, headers=auth_header(token))
    return response.status_code, response.json()


def found_via(api: TestClient, token: str) -> list[str]:
    response = api.post('/search', json=FORM, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK, response.text
    return [r['found_via'] for r in response.json()['results']]


def test_sources_need_a_token(api: TestClient) -> None:
    assert api.get(URL).status_code == status.HTTP_401_UNAUTHORIZED
    assert api.put(URL, json={'sources': None}).status_code == status.HTTP_401_UNAUTHORIZED


def test_by_default_all_sources_are_available_and_nothing_is_chosen(
    api: TestClient, access_token: str
) -> None:
    response = api.get(URL, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        'available': ['tavily', 'jsearch'],
        'chosen': None,
        'features': {'tavily': [], 'jsearch': []},  # fakes use no filter
        'turned_off': [],
    }


def test_by_default_a_search_asks_every_source(api: TestClient, access_token: str) -> None:
    assert found_via(api, access_token) == ['tavily', 'jsearch']


def test_choosing_one_source_is_saved(api: TestClient, access_token: str) -> None:
    code, body = choose(api, access_token, ['jsearch'])

    assert code == status.HTTP_200_OK
    assert body['available'] == ['tavily', 'jsearch']
    assert body['chosen'] == ['jsearch']
    assert api.get(URL, headers=auth_header(access_token)).json()['chosen'] == ['jsearch']


def test_a_search_asks_only_the_chosen_source(api: TestClient, access_token: str) -> None:
    choose(api, access_token, ['jsearch'])

    assert found_via(api, access_token) == ['jsearch']


def test_sources_are_asked_in_the_apps_order_and_repeats_are_dropped(
    api: TestClient, access_token: str
) -> None:
    _, body = choose(api, access_token, ['jsearch', 'tavily', 'jsearch'])

    assert body['chosen'] == ['jsearch', 'tavily']
    assert found_via(api, access_token) == ['tavily', 'jsearch']


def test_null_goes_back_to_all_sources(api: TestClient, access_token: str) -> None:
    choose(api, access_token, ['jsearch'])

    code, body = choose(api, access_token, None)

    assert code == status.HTTP_200_OK
    assert body['chosen'] is None
    assert found_via(api, access_token) == ['tavily', 'jsearch']


def test_unknown_source_returns_422_and_keeps_the_choice(
    api: TestClient, access_token: str
) -> None:
    choose(api, access_token, ['jsearch'])

    code, body = choose(api, access_token, ['tavily', 'google'])

    assert code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert body['detail'] == 'Unknown search source: google'
    assert api.get(URL, headers=auth_header(access_token)).json()['chosen'] == ['jsearch']


@pytest.mark.parametrize('sources', [[], [''], ['x' * 51]])
def test_empty_list_or_bad_name_returns_422(
    api: TestClient, access_token: str, sources: list[str]
) -> None:
    code, _ = choose(api, access_token, sources)

    assert code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_choice_is_per_user(api: TestClient, access_token: str) -> None:
    _, other_token = register_and_login(api, 'other@example.com')
    choose(api, access_token, ['jsearch'])

    assert found_via(api, other_token) == ['tavily', 'jsearch']


def test_chosen_source_turned_off_falls_back_to_all(api: TestClient, access_token: str) -> None:
    choose(api, access_token, ['jsearch'])
    app.dependency_overrides[get_search_sources] = lambda: [
        FakeSearchSource(name='tavily', results=[result('t1')])
    ]  # the admin turned JSearch off

    assert found_via(api, access_token) == ['tavily']


def test_features_say_which_filters_each_source_uses(api: TestClient, access_token: str) -> None:
    jsearch = FakeSearchSource(name='jsearch')
    jsearch.features = frozenset({SourceFeature.COUNTRY, SourceFeature.PAGES})
    app.dependency_overrides[get_search_sources] = lambda: [jsearch]

    body = api.get(URL, headers=auth_header(access_token)).json()

    assert body['features'] == {'jsearch': ['country', 'pages']}
