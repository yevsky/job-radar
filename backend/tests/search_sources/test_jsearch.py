import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.dependencies import get_search_sources
from app.main import app
from app.models.enums import EmploymentType
from app.schemas.search import PostedWithin, SearchQuery
from app.search_sources.base import SearchSourceError
from app.search_sources.jsearch import JSEARCH_URL, JSearchSource, location_of
from app.search_sources.registry import build_sources
from app.search_sources.tavily import TavilySource
from tests.helpers import auth_header

DATA = Path(__file__).parent / 'data'
SAMPLE = json.loads((DATA / 'jsearch.json').read_text(encoding='utf-8'))
TAVILY_SAMPLE = json.loads((DATA / 'tavily.json').read_text(encoding='utf-8'))
QUERY = SearchQuery(position='Python developer')

Handler = Callable[[httpx.Request], httpx.Response]


def mock_client(handler: Handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def make_source(handler: Handler) -> JSearchSource:
    """A JSearchSource whose HTTP client never touches the network: handler answers instead."""
    return JSearchSource(api_key='jsearch-test-key', client=mock_client(handler))


def answer(status: int = 200, body: Any = SAMPLE) -> Handler:
    return lambda _request: httpx.Response(status, json=body)


@pytest.fixture
def requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def recording(requests: list[httpx.Request]) -> JSearchSource:
    """A source that answers with the sample and keeps every request it sent."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=SAMPLE)

    return make_source(handler)


def sent_params(requests: list[httpx.Request]) -> dict[str, str]:
    assert len(requests) == 1
    return dict(requests[0].url.params)


# --- mapping ---------------------------------------------------------------------------


def test_sample_maps_to_offers() -> None:
    offers = make_source(answer()).search(QUERY, 10).offers

    assert [o.title for o in offers] == [
        'Junior Python Developer',
        'Python Backend Engineer',
        'Python Developer (Temporary)',
    ]
    first = offers[0]
    assert first.company_name == 'Codesky'
    assert str(first.url) == 'https://www.linkedin.com/jobs/view/1234567890'
    assert first.location == 'Wrocław, Lower Silesian Voivodeship, Poland'  # job_location
    assert first.employment_type == EmploymentType.FULL_TIME
    assert first.description == 'Build FastAPI services with a small team.'
    assert first.technologies == ['Python', 'FastAPI', 'PostgreSQL']
    assert first.deadline == datetime(2026, 12, 10, tzinfo=UTC)
    assert first.experience_level == 'junior'  # from 'Junior Python Developer'


def test_remote_job_has_remote_location() -> None:
    remote = make_source(answer()).search(QUERY, 10).offers[1]

    assert remote.location == 'Poland (remote)'  # job_location plus remote
    assert remote.employment_type == EmploymentType.CONTRACT
    assert remote.technologies == []  # job_required_skills was null
    assert remote.deadline is None


def test_unknown_employment_type_gives_none() -> None:
    temporary = make_source(answer()).search(QUERY, 10).offers[2]

    assert temporary.employment_type is None


def test_without_job_location_city_and_country_are_used() -> None:
    temporary = make_source(answer()).search(QUERY, 10).offers[2]

    assert temporary.location == 'Kraków, PL'


def test_skill_names_that_are_too_long_are_dropped() -> None:
    temporary = make_source(answer()).search(QUERY, 10).offers[2]

    assert temporary.technologies == ['Django']


def test_broken_job_is_skipped_and_the_rest_returned() -> None:
    offers = make_source(answer()).search(QUERY, 10).offers

    assert len(offers) == 3  # 4 in the sample, the one without employer_name is left out


def test_results_are_cut_to_the_limit() -> None:
    assert len(make_source(answer()).search(QUERY, 2).offers) == 2


def test_remote_job_in_a_city_keeps_the_city() -> None:
    job = {'job_is_remote': True, 'job_location': 'Warszawa, Mazowieckie, Poland'}

    assert location_of(job) == 'Warszawa, Mazowieckie, Poland (remote)'


def test_short_page_has_no_more() -> None:
    assert make_source(answer()).search(QUERY, 10).has_more is False  # 4 jobs of 10


def test_full_page_may_have_more() -> None:
    jobs = SAMPLE['data']['jobs']
    full = {'data': {'jobs': [jobs[0]] * 10}}

    assert make_source(answer(200, full)).search(QUERY, 10).has_more is True


def test_jsearch_uses_every_filter() -> None:
    assert make_source(answer()).features == {'country', 'posted_within', 'pages'}


# --- the request -----------------------------------------------------------------------


def test_request_sends_query_page_country_and_api_key(
    recording: JSearchSource, requests: list[httpx.Request]
) -> None:
    recording.search(QUERY.model_copy(update={'locations': ['Warsaw', 'Wrocław']}), 5)

    request = requests[0]
    assert request.method == 'GET'
    assert request.url.copy_with(query=None) == httpx.URL(JSEARCH_URL)
    assert request.headers['x-api-key'] == 'jsearch-test-key'
    assert sent_params(requests) == {
        'query': 'Python developer Warsaw OR Wrocław',
        'page': '1',
        'num_pages': '1',
        'country': 'pl',
    }


def test_form_country_and_page_are_sent(
    recording: JSearchSource, requests: list[httpx.Request]
) -> None:
    recording.search(QUERY.model_copy(update={'country': 'de', 'page': 3}), 5)

    params = sent_params(requests)
    assert params['country'] == 'de'
    assert params['page'] == '3'


@pytest.mark.parametrize(
    ('posted_within', 'date_posted'),
    [(PostedWithin.DAY, 'today'), (PostedWithin.WEEK, 'week'), (PostedWithin.MONTH, 'month')],
)
def test_posted_within_becomes_date_posted(
    recording: JSearchSource,
    requests: list[httpx.Request],
    posted_within: PostedWithin,
    date_posted: str,
) -> None:
    recording.search(QUERY.model_copy(update={'posted_within': posted_within}), 5)

    assert sent_params(requests)['date_posted'] == date_posted


def test_level_stays_in_the_phrase_and_is_not_a_jsearch_filter(
    recording: JSearchSource, requests: list[httpx.Request]
) -> None:
    """job_requirements gave 0 jobs for Poland; the level is a word in the position instead."""
    recording.search(QUERY.model_copy(update={'position': 'Junior Python developer'}), 5)

    assert 'job_requirements' not in sent_params(requests)
    assert sent_params(requests)['query'] == 'Junior Python developer'


# --- errors ----------------------------------------------------------------------------


@pytest.mark.parametrize('status_code', [401, 403, 429, 500])
def test_http_error_raises_search_source_error(status_code: int) -> None:
    with pytest.raises(SearchSourceError, match=f'JSearch answered {status_code}'):
        make_source(answer(status_code, {'message': 'error'})).search(QUERY, 5)


def test_timeout_raises_search_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout('timed out', request=request)

    with pytest.raises(SearchSourceError, match='could not be reached'):
        make_source(handler).search(QUERY, 5)


@pytest.mark.parametrize(
    'body', [{'status': 'OK'}, {'data': 'nope'}, {'data': {'jobs': 'nope'}}, ['a', 'list']]
)
def test_unexpected_json_raises_search_source_error(body: Any) -> None:
    with pytest.raises(SearchSourceError, match='could not read'):
        make_source(answer(200, body)).search(QUERY, 5)


# --- test() ----------------------------------------------------------------------------


def test_test_is_true_when_jsearch_answers(recording: JSearchSource) -> None:
    assert recording.test() is True


def test_test_is_false_instead_of_raising() -> None:
    assert make_source(answer(403, {'message': 'not subscribed'})).test() is False


# --- registry --------------------------------------------------------------------------


def test_registry_builds_jsearch_with_its_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('app.search_sources.registry.settings.jsearch_api_key', SecretStr('k'))

    [source] = build_sources(['jsearch'])

    assert isinstance(source, JSearchSource)
    assert source.name == 'jsearch'
    assert source.api_key == 'k'
    assert source.country == 'pl'


def test_registry_without_key_fails_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr('app.search_sources.registry.settings.jsearch_api_key', None)

    with pytest.raises(ValueError, match='JSEARCH_API_KEY is empty'):
        build_sources(['jsearch'])


# --- both sources in POST /search ------------------------------------------------------


def test_search_with_tavily_and_jsearch_returns_results_from_both(
    api: TestClient, access_token: str
) -> None:
    tavily = TavilySource(
        api_key='t',
        domains=[],
        client=mock_client(lambda _request: httpx.Response(200, json=TAVILY_SAMPLE)),
    )
    app.dependency_overrides[get_search_sources] = lambda: [tavily, make_source(answer())]

    response = api.post(
        '/search', json={'position': 'Python developer'}, headers=auth_header(access_token)
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['errors'] == []
    found = [(r['found_via'], r['title']) for r in body['results']]
    # The LinkedIn link is in both samples, so it is kept once, from Tavily (asked first).
    assert found == [
        ('tavily', 'Junior Python Developer'),
        ('tavily', 'Python Developer (FastAPI)'),
        ('tavily', 'Python Backend Developer'),
        ('jsearch', 'Python Backend Engineer'),
        ('jsearch', 'Python Developer (Temporary)'),
    ]


def test_one_failing_api_does_not_hide_the_other(api: TestClient, access_token: str) -> None:
    tavily = TavilySource(
        api_key='t',
        domains=[],
        client=mock_client(lambda _request: httpx.Response(401, json={'detail': 'bad key'})),
    )
    app.dependency_overrides[get_search_sources] = lambda: [tavily, make_source(answer())]

    response = api.post(
        '/search', json={'position': 'Python developer'}, headers=auth_header(access_token)
    )

    body = response.json()
    assert body['errors'] == [{'source': 'tavily', 'message': 'Tavily answered 401'}]
    assert {r['found_via'] for r in body['results']} == {'jsearch'}
