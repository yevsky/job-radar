import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.search_sources.page_reader import (
    TAVILY_EXTRACT_URL,
    FakePageReader,
    TavilyPageReader,
    build_page_reader,
)

LINK = 'https://justjoin.it/job-offer/codesky-python-developer-wroclaw-python'
PAGE = {'results': [{'url': LINK, 'raw_content': '  Python Developer at Codesky...  '}]}

Handler = Callable[[httpx.Request], httpx.Response]


def make_reader(handler: Handler) -> TavilyPageReader:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TavilyPageReader(api_key='tvly-test-key', client=client)


def answer(status: int = 200, body: Any = PAGE) -> Handler:
    return lambda _request: httpx.Response(status, json=body)


def test_returns_the_page_text_trimmed() -> None:
    assert make_reader(answer()).read(LINK) == 'Python Developer at Codesky...'


def test_sends_the_link_and_the_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=PAGE)

    make_reader(handler).read(LINK)

    [request] = requests
    assert str(request.url) == TAVILY_EXTRACT_URL
    assert request.headers['Authorization'] == 'Bearer tvly-test-key'
    assert json.loads(request.content)['urls'] == [LINK]


@pytest.mark.parametrize(
    'handler',
    [
        answer(status=401, body={'detail': 'bad key'}),
        answer(status=500, body={}),
        answer(body={'results': [], 'failed_results': [{'url': LINK, 'error': 'blocked'}]}),
        answer(body={'results': [{'url': LINK, 'raw_content': '   '}]}),
        answer(body={'results': [{'url': LINK, 'raw_content': None}]}),
        answer(body={'unexpected': True}),
        answer(body=['not', 'an', 'object']),
        lambda _request: httpx.Response(200, text='<html>not json</html>'),
    ],
    ids=['401', '500', 'failed', 'blank', 'null', 'no-results', 'list', 'html'],
)
def test_any_problem_gives_none(handler: Handler) -> None:
    assert make_reader(handler).read(LINK) is None


def test_no_connection_gives_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError('no route', request=request)

    assert make_reader(handler).read(LINK) is None


def test_timeout_gives_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout('too slow', request=request)

    assert make_reader(handler).read(LINK) is None


def test_reader_is_built_only_with_a_tavily_key() -> None:
    assert isinstance(build_page_reader(SecretStr('tvly-key')), TavilyPageReader)
    assert build_page_reader(SecretStr('')) is None
    assert build_page_reader(None) is None


def test_fake_reader_answers_from_its_pages_and_records_links() -> None:
    reader = FakePageReader({LINK: 'text'})

    assert reader.read(LINK) == 'text'
    assert reader.read('https://example.com/other') is None
    assert reader.urls == [LINK, 'https://example.com/other']
