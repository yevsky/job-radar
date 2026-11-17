from collections.abc import Callable, Mapping

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_search_sources
from app.main import app
from app.models import JobOffer
from app.schemas.job_offer import JobOfferImport
from app.schemas.search import SearchQuery
from app.search_sources.base import SearchSource
from app.search_sources.fake import FakeSearchSource
from app.search_sources.registry import build_sources
from tests.helpers import auth_header

URL = '/search'
FORM = {'position': 'Python developer', 'skills': ['FastAPI'], 'locations': ['Wrocław']}

UseSources = Callable[..., None]


def make_result(path: str, title: str = 'Backend Developer') -> JobOfferImport:
    return JobOfferImport.model_validate(
        {'title': title, 'company_name': 'Codesky', 'url': f'https://example.com/{path}'}
    )


@pytest.fixture
def use_sources(api: TestClient) -> UseSources:
    """Make POST /search use the given sources instead of the ones from settings.

    Depends on `api`, whose teardown clears app.dependency_overrides after the test.
    """
    del api  # requested only for its cleanup

    def use(*sources: SearchSource) -> None:
        app.dependency_overrides[get_search_sources] = lambda: list(sources)

    return use


def search(api: TestClient, token: str, form: Mapping[str, object] = FORM) -> dict[str, object]:
    response = api.post(URL, json=form, headers=auth_header(token))
    assert response.status_code == status.HTTP_200_OK, response.text
    body: dict[str, object] = response.json()
    return body


def result_urls(body: dict[str, object]) -> list[str]:
    results = body['results']
    assert isinstance(results, list)
    return [result['url'] for result in results]


def test_search_without_token_returns_401(api: TestClient) -> None:
    assert api.post(URL, json=FORM).status_code == status.HTTP_401_UNAUTHORIZED


def test_search_returns_results_with_found_via_and_query(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    use_sources(FakeSearchSource(results=[make_result('jobs/1', 'Python Developer')]))

    body = search(api, access_token)

    assert body['query'] == 'Python developer FastAPI Wrocław'
    assert body['errors'] == []
    results = body['results']
    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]['title'] == 'Python Developer'
    assert results[0]['company_name'] == 'Codesky'
    assert results[0]['url'] == 'https://example.com/jobs/1'
    assert results[0]['found_via'] == 'fake'


def test_source_receives_the_form_with_filters(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    source = FakeSearchSource()
    use_sources(source)
    form = {
        **FORM,
        'remote_only': True,
        'posted_within': 'week',
        'employment_types': ['b2b'],
    }

    search(api, access_token, form)

    assert source.queries == [SearchQuery.model_validate(form)]


def test_search_is_not_limited_to_the_profile(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    api.put(
        '/profile/me',
        json={'desired_position': 'Python developer'},
        headers=auth_header(access_token),
    )
    source = FakeSearchSource()
    use_sources(source)

    body = search(api, access_token, {'position': 'Data engineer'})

    assert body['query'] == 'Data engineer'
    assert source.queries[0].position == 'Data engineer'


def test_search_saves_nothing(
    api: TestClient, access_token: str, use_sources: UseSources, db: Session
) -> None:
    use_sources(FakeSearchSource(results=[make_result('jobs/1'), make_result('jobs/2')]))
    count = select(func.count()).select_from(JobOffer)
    before = db.scalar(count)

    search(api, access_token)

    assert db.scalar(count) == before


def test_same_link_from_two_sources_is_returned_once(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    use_sources(
        FakeSearchSource(name='tavily', results=[make_result('jobs/1'), make_result('jobs/2')]),
        FakeSearchSource(
            name='jsearch',
            results=[make_result('jobs/1/?utm_source=x'), make_result('jobs/3')],
        ),
    )

    body = search(api, access_token)

    assert result_urls(body) == [
        'https://example.com/jobs/1',
        'https://example.com/jobs/2',
        'https://example.com/jobs/3',
    ]
    results = body['results']
    assert isinstance(results, list)
    assert [r['found_via'] for r in results] == ['tavily', 'tavily', 'jsearch']


def test_failing_source_is_reported_and_others_still_work(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    use_sources(
        FakeSearchSource(name='tavily', fail=True),
        FakeSearchSource(name='jsearch', results=[make_result('jobs/1')]),
    )

    body = search(api, access_token)

    assert result_urls(body) == ['https://example.com/jobs/1']
    assert body['errors'] == [{'source': 'tavily', 'message': 'tavily is set to fail'}]


def test_all_sources_failing_returns_200_with_errors(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    use_sources(
        FakeSearchSource(name='tavily', fail=True),
        FakeSearchSource(name='jsearch', fail=True),
    )

    body = search(api, access_token)

    assert body['results'] == []
    errors = body['errors']
    assert isinstance(errors, list)
    assert [error['source'] for error in errors] == ['tavily', 'jsearch']


def test_results_per_source_are_limited(
    api: TestClient,
    access_token: str,
    use_sources: UseSources,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('app.routers.search.settings.search_results_per_source', 2)
    use_sources(FakeSearchSource(results=[make_result(f'jobs/{n}') for n in range(5)]))

    body = search(api, access_token)

    assert len(result_urls(body)) == 2


@pytest.mark.parametrize(
    'form',
    [
        {},
        {'locations': ['Wrocław']},
        {'position': '   ', 'skills': [' ']},
    ],
)
def test_form_without_position_and_skills_returns_422(
    api: TestClient, access_token: str, use_sources: UseSources, form: dict[str, object]
) -> None:
    source = FakeSearchSource()
    use_sources(source)

    response = api.post(URL, json=form, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert response.json()['detail'] == 'Add a position or at least one skill'
    assert source.queries == []  # no source was asked


def test_too_many_skills_returns_422(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    use_sources(FakeSearchSource())
    form = {'skills': [f'Skill {n}' for n in range(11)]}

    response = api.post(URL, json=form, headers=auth_header(access_token))

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# GET /admin/search-sources


def test_admin_sees_each_source_and_whether_it_works(
    api: TestClient, admin_token: str, use_sources: UseSources
) -> None:
    use_sources(FakeSearchSource(name='tavily'), FakeSearchSource(name='jsearch', fail=True))

    response = api.get('/admin/search-sources', headers=auth_header(admin_token))

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [
        {'name': 'tavily', 'ok': True},
        {'name': 'jsearch', 'ok': False},
    ]


def test_normal_user_cannot_check_sources(api: TestClient, access_token: str) -> None:
    response = api.get('/admin/search-sources', headers=auth_header(access_token))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_fake_source_from_the_registry_returns_demo_results(
    api: TestClient, access_token: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 'fake' source as the registry builds it; SEARCH_SOURCES in .env doesn't matter."""
    monkeypatch.setattr('app.dependencies.search_sources', build_sources(['fake']))

    body = search(api, access_token)

    assert len(result_urls(body)) == 8


def test_offers_far_from_the_wanted_level_are_left_out(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    titles = [
        'Junior Python Developer',
        'Python Intern',
        'Mid Python Developer',
        'Senior Python Developer',
        'Lead Python Engineer',
        'Python Developer',
    ]
    use_sources(
        FakeSearchSource(results=[make_result(f'jobs/{i}', t) for i, t in enumerate(titles)])
    )

    body = search(api, access_token, {'position': 'Python developer', 'experience_level': 'junior'})

    results = body['results']
    assert isinstance(results, list)
    assert [r['title'] for r in results] == [
        'Junior Python Developer',
        'Python Intern',
        'Mid Python Developer',
        'Python Developer',  # level unknown: kept
    ]


def test_without_a_level_nothing_is_left_out(
    api: TestClient, access_token: str, use_sources: UseSources
) -> None:
    use_sources(FakeSearchSource(results=[make_result('jobs/1', 'Senior Python Developer')]))

    body = search(api, access_token, {'position': 'Python developer'})

    assert len(result_urls(body)) == 1
