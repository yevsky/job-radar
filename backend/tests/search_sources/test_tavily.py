import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.models.enums import EmploymentType
from app.schemas.search import PostedWithin, SearchQuery
from app.search_sources.base import SearchSourceError
from app.search_sources.registry import build_sources
from app.search_sources.tavily import TAVILY_URL, TavilySource, split_title, to_offer

SAMPLE = json.loads((Path(__file__).parent / 'data' / 'tavily.json').read_text(encoding='utf-8'))
QUERY = SearchQuery(position='Python developer', skills=['FastAPI'])
DOMAINS = ['justjoin.it', 'nofluffjobs.com']

Handler = Callable[[httpx.Request], httpx.Response]


def make_source(handler: Handler) -> TavilySource:
    """A TavilySource whose HTTP client never touches the network: handler answers instead."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TavilySource(api_key='tvly-test-key', domains=DOMAINS, client=client)


def answer(status: int = 200, body: Any = SAMPLE) -> Handler:
    return lambda _request: httpx.Response(status, json=body)


@pytest.fixture
def requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def recording(requests: list[httpx.Request]) -> TavilySource:
    """A source that answers with the sample and keeps every request it sent."""

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=SAMPLE)

    return make_source(handler)


def sent_body(requests: list[httpx.Request]) -> dict[str, Any]:
    assert len(requests) == 1
    return dict(json.loads(requests[0].content))


# --- mapping ---------------------------------------------------------------------------


def test_sample_maps_to_offers() -> None:
    offers = make_source(answer()).search(QUERY, 10)

    assert [(o.title, o.company_name, str(o.url)) for o in offers] == [
        ('Junior Python Developer', 'Codesky', 'https://www.linkedin.com/jobs/view/1234567890'),
        (
            'Python Developer (FastAPI)',
            'Northwind Data',
            'https://justjoin.it/job-offer/northwind-data-python-developer-fastapi-wroclaw',
        ),
        (
            'Python Backend Developer',
            'nofluffjobs.com',
            'https://nofluffjobs.com/pl/job/python-backend-developer-wroclaw-abc123',
        ),
    ]
    assert offers[0].description is not None
    assert offers[0].description.startswith('Codesky is hiring')


def test_broken_result_is_skipped_and_the_rest_returned() -> None:
    offers = make_source(answer()).search(QUERY, 10)

    assert len(offers) == 3  # 4 in the sample, the one with 'not a link' is left out
    assert all(o.title != 'Broken result without a link' for o in offers)


def test_results_are_cut_to_the_limit() -> None:
    assert len(make_source(answer()).search(QUERY, 2)) == 2


@pytest.mark.parametrize(
    ('page_title', 'expected'),
    [
        ('Python Developer at Codesky | LinkedIn', ('Python Developer', 'Codesky')),
        ('Python Developer - Codesky - Just Join IT', ('Python Developer', 'Codesky')),
        ('Python Developer – Codesky', ('Python Developer', 'Codesky')),
        ('Python Developer', ('Python Developer', None)),
        (
            'Back-end developer',
            ('Back-end developer', None),
        ),  # a hyphen inside a word is not a dash
    ],
)
def test_split_title(page_title: str, expected: tuple[str, str | None]) -> None:
    assert split_title(page_title) == expected


@pytest.mark.parametrize(
    'row',
    [
        None,
        'text',
        {},
        {'title': 'Dev', 'url': 'not a link'},
        {'title': '', 'url': 'https://a.pl/1'},
    ],
)
def test_rows_that_are_not_offers_give_none(row: object) -> None:
    assert to_offer(row) is None


# --- the request -----------------------------------------------------------------------


def test_request_sends_query_domains_and_key(
    recording: TavilySource, requests: list[httpx.Request]
) -> None:
    recording.search(QUERY, 5)

    request = requests[0]
    assert request.method == 'POST'
    assert str(request.url) == TAVILY_URL
    assert request.headers['Authorization'] == 'Bearer tvly-test-key'
    body = sent_body(requests)
    assert body['query'] == 'Python developer FastAPI'
    assert body['max_results'] == 5
    assert body['include_domains'] == DOMAINS
    assert 'time_range' not in body


def test_posted_within_becomes_time_range(
    recording: TavilySource, requests: list[httpx.Request]
) -> None:
    recording.search(QUERY.model_copy(update={'posted_within': PostedWithin.WEEK}), 5)

    assert sent_body(requests)['time_range'] == 'week'


def test_employment_types_are_added_to_the_phrase(
    recording: TavilySource, requests: list[httpx.Request]
) -> None:
    query = QUERY.model_copy(
        update={'employment_types': [EmploymentType.B2B, EmploymentType.FULL_TIME]}
    )

    recording.search(query, 5)

    assert sent_body(requests)['query'] == 'Python developer FastAPI B2B full-time'


def test_max_results_is_at_most_20(recording: TavilySource, requests: list[httpx.Request]) -> None:
    recording.search(QUERY, 50)

    assert sent_body(requests)['max_results'] == 20


def test_no_domains_sends_no_include_domains(requests: list[httpx.Request]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=SAMPLE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    TavilySource(api_key='k', domains=[], client=client).search(QUERY, 5)

    assert 'include_domains' not in sent_body(requests)


# --- errors ----------------------------------------------------------------------------


@pytest.mark.parametrize('status', [401, 429, 500])
def test_http_error_raises_search_source_error(status: int) -> None:
    with pytest.raises(SearchSourceError, match=f'Tavily answered {status}'):
        make_source(answer(status, {'detail': 'error'})).search(QUERY, 5)


def test_timeout_raises_search_source_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout('timed out', request=request)

    with pytest.raises(SearchSourceError, match='could not be reached'):
        make_source(handler).search(QUERY, 5)


@pytest.mark.parametrize('body', [{'no_results': []}, {'results': 'nope'}, ['a', 'list']])
def test_unexpected_json_raises_search_source_error(body: Any) -> None:
    with pytest.raises(SearchSourceError, match='could not read'):
        make_source(answer(200, body)).search(QUERY, 5)


def test_response_that_is_not_json_raises_search_source_error() -> None:
    source = make_source(lambda _request: httpx.Response(200, text='<html>oops</html>'))

    with pytest.raises(SearchSourceError, match='could not read'):
        source.search(QUERY, 5)


def test_error_message_does_not_contain_the_key() -> None:
    with pytest.raises(SearchSourceError) as info:
        make_source(answer(401, {'detail': 'bad key'})).search(QUERY, 5)

    assert 'tvly-test-key' not in str(info.value)


# --- test() ----------------------------------------------------------------------------


def test_test_is_true_when_tavily_answers(
    recording: TavilySource, requests: list[httpx.Request]
) -> None:
    assert recording.test() is True
    assert sent_body(requests)['max_results'] == 1


def test_test_is_false_instead_of_raising() -> None:
    assert make_source(answer(401, {'detail': 'bad key'})).test() is False


# --- registry --------------------------------------------------------------------------


def test_registry_builds_tavily_with_key_and_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('app.search_sources.registry.settings.tavily_api_key', SecretStr('tvly-x'))
    monkeypatch.setattr('app.search_sources.registry.settings.tavily_domains', ['pracuj.pl'])

    [source] = build_sources(['tavily'])

    assert isinstance(source, TavilySource)
    assert source.name == 'tavily'
    assert source.api_key == 'tvly-x'
    assert source.domains == ['pracuj.pl']


@pytest.mark.parametrize('key', [None, SecretStr(''), SecretStr('   ')])
def test_registry_without_key_fails_with_a_clear_message(
    monkeypatch: pytest.MonkeyPatch, key: SecretStr | None
) -> None:
    monkeypatch.setattr('app.search_sources.registry.settings.tavily_api_key', key)

    with pytest.raises(ValueError, match='TAVILY_API_KEY is empty'):
        build_sources(['tavily'])
