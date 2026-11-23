import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest

from app.ai.base import AIProvider, AIProviderError, ChatMessage
from app.ai.openai_compat import MAX_ANSWER_TOKENS, OpenAICompatProvider

BASE_URL = 'http://ollama.test/v1'
MESSAGES = [
    ChatMessage(role='system', content='Answer only with JSON.'),
    ChatMessage(role='user', content='We need a Python developer.'),
    ChatMessage(role='assistant', content='{"skills": []}'),
]

Handler = Callable[[httpx2.Request], httpx2.Response]


def completion(content: str | None, finish_reason: str = 'stop') -> dict[str, Any]:
    """The body an OpenAI-compatible server sends back for one chat answer."""
    return {
        'id': 'chatcmpl-1',
        'object': 'chat.completion',
        'created': 0,
        'model': 'qwen2.5:3b',
        'choices': [
            {
                'index': 0,
                'message': {'role': 'assistant', 'content': content},
                'finish_reason': finish_reason,
            }
        ],
    }


def model_list(*ids: str) -> dict[str, Any]:
    return {
        'object': 'list',
        'data': [{'id': i, 'object': 'model', 'created': 0, 'owned_by': 'x'} for i in ids],
    }


def make_provider(
    handler: Handler, model: str = 'qwen2.5:3b', max_tokens: int | None = None
) -> OpenAICompatProvider:
    """A provider whose HTTP client never touches the network: handler answers instead."""
    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return OpenAICompatProvider(
        name='ollama',
        base_url=BASE_URL,
        api_key='test-key',
        model=model,
        timeout=5,
        http_client=client,
        max_tokens=max_tokens,
    )


def answer(status: int = 200, body: Any = None) -> Handler:
    return lambda _request: httpx2.Response(status, json=body)


@pytest.fixture
def requests() -> list[httpx2.Request]:
    return []


def recording(requests: list[httpx2.Request], body: Any) -> OpenAICompatProvider:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=body)

    return make_provider(handler)


# chat


def test_chat_returns_the_answer_text() -> None:
    provider = make_provider(answer(body=completion('{"skills": ["Python"]}')))
    assert provider.chat(MESSAGES) == '{"skills": ["Python"]}'


def test_chat_sends_model_messages_temperature_and_json_mode(
    requests: list[httpx2.Request],
) -> None:
    provider = recording(requests, completion('{}'))

    provider.chat(MESSAGES)

    [request] = requests
    assert request.method == 'POST'
    assert str(request.url) == f'{BASE_URL}/chat/completions'
    assert request.headers['Authorization'] == 'Bearer test-key'
    body = json.loads(request.content)
    assert body['model'] == 'qwen2.5:3b'
    assert body['temperature'] == 0
    assert body['response_format'] == {'type': 'json_object'}
    assert body['messages'] == [
        {'role': 'system', 'content': 'Answer only with JSON.'},
        {'role': 'user', 'content': 'We need a Python developer.'},
        {'role': 'assistant', 'content': '{"skills": []}'},
    ]


def test_chat_without_json_mode_sends_no_response_format(
    requests: list[httpx2.Request],
) -> None:
    provider = recording(requests, completion('Hello!'))

    assert provider.chat(MESSAGES, json_mode=False) == 'Hello!'
    assert 'response_format' not in json.loads(requests[0].content)


@pytest.mark.parametrize('status', [400, 401, 404, 429, 500, 503])
def test_error_status_becomes_provider_error(status: int) -> None:
    provider = make_provider(answer(status, {'error': {'message': 'nope'}}))
    with pytest.raises(AIProviderError, match=f'HTTP {status}'):
        provider.chat(MESSAGES)


def test_the_apis_reason_is_part_of_the_error() -> None:
    """Gemini sends its errors as a list; the reason must still come through."""
    body = [{'error': {'code': 400, 'message': 'Invalid JSON payload: "title"', 'status': 'X'}}]
    provider = make_provider(answer(400, body))
    with pytest.raises(AIProviderError, match='HTTP 400: .*Invalid JSON payload'):
        provider.chat(MESSAGES)


def test_server_error_is_not_retried(requests: list[httpx2.Request]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(500, json={'error': {'message': 'boom'}})

    with pytest.raises(AIProviderError):
        make_provider(handler).chat(MESSAGES)
    assert len(requests) == 1


def test_connection_refused_becomes_provider_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError('Connection refused', request=request)

    with pytest.raises(AIProviderError, match='Cannot reach ollama at http://ollama.test/v1'):
        make_provider(handler).chat(MESSAGES)


def test_timeout_becomes_provider_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout('too slow', request=request)

    with pytest.raises(AIProviderError, match='did not answer in time'):
        make_provider(handler).chat(MESSAGES)


@pytest.mark.parametrize('content', [None, '', '   '])
def test_empty_answer_becomes_provider_error(content: str | None) -> None:
    provider = make_provider(answer(body=completion(content)))
    with pytest.raises(AIProviderError, match='empty answer'):
        provider.chat(MESSAGES)


def test_answer_without_choices_becomes_provider_error() -> None:
    body = completion('x') | {'choices': []}
    with pytest.raises(AIProviderError, match='empty answer'):
        make_provider(answer(body=body)).chat(MESSAGES)


def test_broken_response_body_becomes_provider_error() -> None:
    provider = make_provider(lambda _request: httpx2.Response(200, text='<html>not json</html>'))
    with pytest.raises(AIProviderError, match='not a chat answer'):
        provider.chat(MESSAGES)


def test_test_is_false_for_a_broken_model_list() -> None:
    provider = make_provider(lambda _request: httpx2.Response(200, text='<html>not json</html>'))
    assert provider.test() is False


# test()


def test_test_is_true_when_the_model_is_listed(requests: list[httpx2.Request]) -> None:
    provider = recording(requests, model_list('llama3:8b', 'qwen2.5:3b'))

    assert provider.test() is True
    assert str(requests[0].url) == f'{BASE_URL}/models'  # no prompt, no model loading


def test_test_understands_gemini_model_names() -> None:
    provider = make_provider(answer(body=model_list('models/gemini-2.5-flash')), 'gemini-2.5-flash')
    assert provider.test() is True


def test_test_is_false_when_the_model_is_not_pulled() -> None:
    assert make_provider(answer(body=model_list('llama3:8b'))).test() is False


def test_test_is_false_for_a_wrong_key() -> None:
    assert make_provider(answer(401, {'error': {'message': 'bad key'}})).test() is False


def test_test_is_false_when_the_server_is_down() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError('Connection refused', request=request)

    assert make_provider(handler).test() is False


# shape


def test_provider_keeps_name_model_and_address() -> None:
    provider: AIProvider = make_provider(answer(body=model_list()))  # mypy checks the type too
    assert (provider.name, provider.model, provider.base_url) == ('ollama', 'qwen2.5:3b', BASE_URL)


def test_an_answer_cut_off_at_the_token_limit_is_an_error() -> None:
    """A small model in JSON mode can repeat itself until the limit: say so, don't parse it."""
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json=completion('{"requirements": [', 'length'))

    with pytest.raises(AIProviderError, match='stopped before finishing'):
        make_provider(handler, max_tokens=MAX_ANSWER_TOKENS).chat(
            [ChatMessage(role='user', content='hi')]
        )
    assert bodies[0]['max_tokens'] == MAX_ANSWER_TOKENS


def test_without_a_limit_no_max_tokens_is_sent() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json=completion('{}'))

    make_provider(handler).chat([ChatMessage(role='user', content='hi')])
    assert 'max_tokens' not in bodies[0]
