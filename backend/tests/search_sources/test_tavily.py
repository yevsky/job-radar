import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.schemas.search import PostedWithin, SearchQuery
from app.search_sources.base import SearchSourceError
from app.search_sources.registry import build_sources
from app.search_sources.tavily import (
    TAVILY_URL,
    TavilySource,
    company_from_url,
    is_closed,
    is_offer_page,
    is_only_a_place,
    location_from_url,
    page_text,
    read_row,
    split_title,
    to_offer,
)

SAMPLE = json.loads((Path(__file__).parent / 'data' / 'tavily.json').read_text(encoding='utf-8'))
QUERY = SearchQuery(position='Python developer')
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
    offers = make_source(answer()).search(QUERY, 10).offers

    assert [(o.title, o.company_name, str(o.url)) for o in offers] == [
        ('Junior Python Developer', 'Codesky', 'https://www.linkedin.com/jobs/view/1234567890'),
        (
            'Python Developer (FastAPI)',
            'Northwind Data',
            'https://justjoin.it/job-offer/northwind-data-python-developer-fastapi-wroclaw-python',
        ),
        (
            'Python Backend Developer',
            'Blue Fjord',
            'https://nofluffjobs.com/pl/job/python-backend-developer-blue-fjord-wroclaw-2',
        ),
    ]
    assert offers[0].description is not None
    assert offers[0].description.startswith('Codesky is hiring')
    # Tavily sends no location: the city is read from the link
    assert [o.location for o in offers] == [None, 'Wrocław', 'Wrocław']


def test_broken_result_is_skipped_and_the_rest_returned() -> None:
    offers = make_source(answer()).search(QUERY, 10).offers

    assert len(offers) == 3  # 5 in the sample: a list page and one with 'not a link' are left out
    assert all(o.title != 'Broken result without a link' for o in offers)


def test_list_pages_are_skipped() -> None:
    offers = make_source(answer()).search(QUERY, 10).offers

    assert all('/wroclaw/python' not in str(o.url) for o in offers)


@pytest.mark.parametrize(
    ('url', 'expected'),
    [
        ('https://justjoin.it/job-offer/codesky-python-developer-wroclaw-python', True),
        ('https://justjoin.it/job-offers/warszawa/python', False),
        ('https://nofluffjobs.com/job/python-developer-codesky-warszawa', True),
        ('https://nofluffjobs.com/pl/job/python-developer-codesky-warszawa', True),
        ('https://nofluffjobs.com/warsaw/django', False),
        ('https://nofluffjobs.com/django', False),
        ('https://www.pracuj.pl/praca/python-developer-warszawa,oferta,1004412345', True),
        ('https://www.pracuj.pl/praca/python%20developer;kw/warszawa;wp', False),
        ('https://pl.linkedin.com/jobs/view/python-developer-at-codesky-4306190000', True),
        ('https://www.linkedin.com/jobs/search?keywords=python', False),
        ('https://careers.codesky.local/jobs/42', True),  # not a known board: kept
    ],
)
def test_is_offer_page(url: str, expected: bool) -> None:
    assert is_offer_page(url) is expected


@pytest.mark.parametrize(
    ('title', 'url', 'company'),
    [
        (
            'Python Developer with Azure',
            'https://justjoin.it/job-offer/dcg-python-developer-with-azure-warszawa-python-5d69f599',
            'Dcg',
        ),
        (
            'Python Django Developer',
            'https://nofluffjobs.com/job/python-django-developer-britenet-warszawa-1',
            'Britenet',
        ),
        (
            'Python+Django Senior Developer',
            'https://nofluffjobs.com/job/python-django-senior-developer-van-cargo-warszawa',
            'Van Cargo',
        ),
        (
            'Senior Python Developer',
            'https://pl.linkedin.com/jobs/view/senior-python-developer-at-jobgether-4306190000',
            'Jobgether',
        ),
        ('Python Developer', 'https://nofluffjobs.com/job/python-developer', None),
        ('Python Developer', 'https://careers.codesky.local/jobs/42', None),
    ],
)
def test_company_from_url(title: str, url: str, company: str | None) -> None:
    assert company_from_url(url, title) == company


def test_every_result_is_returned_whatever_the_limit() -> None:
    """Few results survive the list-page and city filters, so Tavily's are never cut."""
    assert len(make_source(answer()).search(QUERY, 2).offers) == 3


@pytest.mark.parametrize(
    ('page_title', 'expected'),
    [
        ('Python Developer at Codesky | LinkedIn', ('Python Developer', 'Codesky')),
        ('Python Developer - Codesky - Just Join IT', ('Python Developer', 'Codesky')),
        ('Python Developer – Codesky', ('Python Developer', 'Codesky')),
        ('Python Developer', ('Python Developer', None)),
        ('Python Developer - Just Join IT', ('Python Developer', None)),  # a site, not a company
        (
            'Python Developer at Netrolynx AI — United States - Jobs - LinkedIn',
            ('Python Developer', 'Netrolynx AI'),
        ),  # LinkedIn's place and site name after the company
        (
            'Python Developer at O2 Technologies,Inc - LinkedIn',
            ('Python Developer', 'O2 Technologies,Inc'),
        ),
        ('Python Django Developer Job', ('Python Django Developer', None)),
        ('Senior Python Developer (remote ...', ('Senior Python Developer (remote', None)),
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
    assert body['query'] == 'Python developer'
    assert body['max_results'] == 20  # always the most: 1 credit whatever the count
    assert body['include_raw_content'] == 'text'  # the full page, still 1 credit
    assert body['include_domains'] == DOMAINS
    assert 'country' not in body  # include_domains already picks the boards
    assert 'time_range' not in body


def test_posted_within_becomes_time_range(
    recording: TavilySource, requests: list[httpx.Request]
) -> None:
    recording.search(QUERY.model_copy(update={'posted_within': PostedWithin.WEEK}), 5)

    assert sent_body(requests)['time_range'] == 'week'


def test_tavily_has_one_page() -> None:
    assert make_source(answer()).search(QUERY, 10).has_more is False


def test_second_page_sends_nothing(recording: TavilySource, requests: list[httpx.Request]) -> None:
    page = recording.search(QUERY.model_copy(update={'page': 2}), 10)

    assert page.offers == []
    assert page.has_more is False
    assert requests == []  # no credit spent


@pytest.mark.parametrize(
    'page_title',
    [
        'General Dynamics Jobs in United States (11,000+ Open Roles)',
        'Python Developer Jobs in Warsaw',
        'Python Developer - 1,234 jobs',
        'Oferty pracy Python Developer',
    ],
)
def test_titles_of_list_pages_are_skipped(page_title: str) -> None:
    assert to_offer({'title': page_title, 'url': 'https://jobs.example.com/x'}) is None


def test_a_normal_title_is_an_offer() -> None:
    assert to_offer({'title': 'Python Developer (3 years)', 'url': 'https://a.example/1'})


@pytest.mark.parametrize(
    ('url', 'page_title', 'wanted', 'location'),
    [
        ('https://justjoin.it/job-offer/codesky-python-dev-warszawa-python', '', [], 'Warszawa'),
        ('https://nofluffjobs.com/pl/job/python-dev-codesky-krakow-1', '', [], 'Kraków'),
        (
            'https://www.pracuj.pl/praca/python-developer-gdansk,oferta,1004',
            '',
            [],
            'Gdańsk',
        ),
        (
            'https://www.linkedin.com/jobs/view/1',
            'Python Developer at Codesky — Wrocław - LinkedIn',
            [],
            'Wrocław',
        ),
        ('https://justjoin.it/job-offer/codesky-python-dev-remote-python', '', [], 'Remote'),
        ('https://example.com/jobs/python-dev-lisbon', '', ['Lisbon'], 'Lisbon'),
        ('https://example.com/jobs/42', 'Python Developer', [], None),
    ],
)
def test_location_from_url(url: str, page_title: str, wanted: list[str], location: str) -> None:
    assert location_from_url(url, page_title, wanted) == location


def test_tavily_uses_only_the_date_filter() -> None:
    assert make_source(answer()).features == {'posted_within'}


def test_list_pages_are_hidden_with_the_reason_and_broken_rows_skipped() -> None:
    page = make_source(answer()).search(QUERY, 10)

    assert [(h.offer.title, h.reason) for h in page.hidden] == [
        ('Python Jobs Wrocław', 'list_page')
    ]
    assert page.skipped == 1  # the row with 'not a link' can't even be shown


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


def test_level_is_read_from_the_title_or_years() -> None:
    junior = to_offer({'title': 'Junior Python Developer', 'url': 'https://example.com/1'})
    by_years = to_offer(
        {'title': 'Python Developer', 'url': 'https://example.com/2', 'content': '6+ years'}
    )
    unknown = to_offer({'title': 'Python Developer', 'url': 'https://example.com/3'})

    assert junior is not None
    assert junior.experience_level == 'junior'
    assert by_years is not None
    assert by_years.experience_level == 'senior'
    assert unknown is not None
    assert unknown.experience_level is None


# --- full pages, closed and expired offers -------------------------------------------------

NFJ_OFFER = 'https://nofluffjobs.com/pl/job/junior-python-developer-masterborn-wroclaw'
LINKEDIN_OFFER = 'https://pl.linkedin.com/jobs/view/junior-python-developer-at-capgemini-123'


def row(
    title: str, url: str = NFJ_OFFER, content: str = '', raw: str | None = None
) -> dict[str, Any]:
    return {'title': title, 'url': url, 'content': content, 'raw_content': raw}


def test_the_full_page_becomes_the_description() -> None:
    raw = 'Junior Python Developer\n\n\n  Stack: Python, FastAPI  \n\nB2B 50-80 PLN/h'
    offer = to_offer(row('Junior Python Developer', content='short snippet', raw=raw))

    assert offer is not None
    assert offer.description == 'Junior Python Developer\nStack: Python, FastAPI\nB2B 50-80 PLN/h'


def test_the_snippet_is_kept_when_there_is_no_full_page() -> None:
    offer = to_offer(row('Junior Python Developer', content='short snippet'))
    assert offer is not None
    assert offer.description == 'short snippet'


def test_a_long_page_is_cut_to_the_description_limit() -> None:
    text = page_text('x' * 30_000)
    assert text is not None
    assert len(text) == 20_000


@pytest.mark.parametrize('raw', [None, 42, '', ' \n \n'])
def test_page_text_without_text_is_none(raw: object) -> None:
    assert page_text(raw) is None


@pytest.mark.parametrize(
    ('snippet', 'raw'),
    [
        ('Capgemini · Wrocław · No longer accepting applications', None),
        ('', 'Junior Python Developer\nCapgemini\nNo longer accepting applications'),
        ('Ta oferta wygasła.', None),
        ('', 'Nie przyjmuje już aplikacji'),
    ],
)
def test_closed_offers_are_skipped(snippet: str, raw: str | None) -> None:
    assert to_offer(row('Junior Python Developer', LINKEDIN_OFFER, snippet, raw)) is None


def test_closed_only_looks_at_the_top_of_the_page() -> None:
    """Further down, pages list other offers, some of them closed."""
    raw = 'Junior Python Developer\n' + 'x' * 3_000 + '\nNo longer accepting applications'
    assert not is_closed('', raw)
    assert to_offer(row('Junior Python Developer', raw=raw)) is not None


def test_an_expired_offer_redirected_to_a_list_is_skipped() -> None:
    """No Fluff Jobs sends an expired offer's link to a search page titled with the city."""
    assert to_offer(row('Wroclaw', content='Junior Python Developer. B2B 6 000 PLN')) is None


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Wroclaw', True),
        ('Wrocław, Poland', True),
        ('Remote', True),
        ('Bielsko-Biała', True),
        ('Python Developer', False),
        ('Capgemini', False),
        ('', False),
    ],
)
def test_is_only_a_place(text: str, expected: bool) -> None:
    assert is_only_a_place(text) is expected


@pytest.mark.parametrize(
    ('page_title', 'expected'),
    [
        (
            'Junior Python Developer w firmie Capgemini - Wrocław',
            ('Junior Python Developer', 'Capgemini'),
        ),
        ('Junior Python Developer - Wrocław', ('Junior Python Developer', None)),
    ],
)
def test_split_title_polish_company_and_a_city_after_the_dash(
    page_title: str, expected: tuple[str, str | None]
) -> None:
    assert split_title(page_title) == expected


def test_a_city_is_never_the_company() -> None:
    offer = to_offer(
        row('Junior Python Developer - Wrocław', 'https://www.pracuj.pl/praca/x,oferta,1004412345')
    )
    assert offer is not None
    assert offer.company_name != 'Wrocław'


@pytest.mark.parametrize(
    ('found', 'reason'),
    [
        (row('Junior Python Developer', content='No longer accepting applications'), 'closed'),
        (row('Wroclaw', content='Junior Python Developer'), 'expired'),
        (row('Python Jobs in Wrocław', 'https://nofluffjobs.com/pl/wroclaw/python'), 'list_page'),
        (row('Junior Python Developer'), None),
    ],
)
def test_read_row_says_why_a_result_is_hidden(found: dict[str, Any], reason: str | None) -> None:
    offer, why = read_row(found)
    assert offer is not None  # still readable, so the user can look at it
    assert why == reason


def test_closed_offers_are_in_the_hidden_list() -> None:
    body = {'results': [row('Junior Python Developer', LINKEDIN_OFFER, 'Offer expired')]}
    page = make_source(answer(body=body)).search(QUERY, 10)

    assert page.offers == []
    assert [(str(h.offer.url), h.reason) for h in page.hidden] == [(LINKEDIN_OFFER, 'closed')]
