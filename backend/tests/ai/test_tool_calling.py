"""chat_tools in every provider: tools go out, tool calls come back, results go back in."""

import json
from typing import Any

import httpx2
import pytest

from app.ai.base import (
    AIProvider,
    AIProviderError,
    ChatMessage,
    ToolCall,
    ToolMessage,
    ToolResult,
    ToolSpec,
    ToolTurn,
)
from app.ai.fake import FakeAIProvider
from app.ai.openai_compat import SKIP_SIGNATURE
from tests.ai.test_anthropic_provider import THINKING, message, text
from tests.ai.test_anthropic_provider import make_provider as make_anthropic
from tests.ai.test_anthropic_provider import sent as sent_anthropic
from tests.ai.test_openai_compat import make_provider as make_openai

TOOLS = [
    ToolSpec(
        name='list_applications',
        description='List your applications.',
        parameters={'type': 'object', 'properties': {'status': {'type': 'string'}}},
    )
]
CALL = ToolCall(id='call_1', name='list_applications', arguments={'status': 'interview'})
HISTORY: list[ToolMessage] = [
    ChatMessage(role='system', content='You help a job seeker.'),
    ChatMessage(role='user', content='Which interviews do I have?'),
    ToolTurn(text='', tool_calls=[CALL]),
    ToolResult(call_id='call_1', content='[{"id": 3}]'),
]


def recording(make: Any, requests: list[httpx2.Request], body: Any) -> Any:
    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json=body)

    return make(handler)


def body_of(request: httpx2.Request) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(request.content)
    return data


# --- the default ----------------------------------------------------------------------------


def test_a_provider_without_tool_support_raises() -> None:
    class TextOnly(AIProvider):
        name = 'text-only'
        model = 'x'

        def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
            del messages, json_mode
            return ''

        def test(self) -> bool:
            return True

    with pytest.raises(AIProviderError, match='cannot call tools'):
        TextOnly().chat_tools(HISTORY, TOOLS)


# --- fake -----------------------------------------------------------------------------------


def test_fake_plays_its_turns_in_order_and_repeats_the_last() -> None:
    first = ToolTurn(tool_calls=[CALL])
    last = ToolTurn(text='You have one interview.')
    fake = FakeAIProvider(turns=[first, last])
    assert fake.chat_tools(HISTORY, TOOLS) is first
    assert fake.chat_tools(HISTORY, TOOLS) is last
    assert fake.chat_tools(HISTORY, TOOLS) is last
    assert fake.tool_specs[0] == TOOLS
    assert fake.tool_calls[0] == HISTORY


def test_fake_answers_with_text_by_default() -> None:
    assert FakeAIProvider().chat_tools(HISTORY, TOOLS).text


def test_fake_set_to_fail_raises() -> None:
    with pytest.raises(AIProviderError):
        FakeAIProvider(fail=True).chat_tools(HISTORY, TOOLS)


# --- OpenAI-compatible ----------------------------------------------------------------------


def completion(content: str | None, tool_calls: list[dict[str, Any]] | None = None) -> Any:
    message: dict[str, Any] = {'role': 'assistant', 'content': content}
    if tool_calls is not None:
        message['tool_calls'] = tool_calls
    return {
        'id': 'chatcmpl-1',
        'object': 'chat.completion',
        'created': 0,
        'model': 'qwen2.5:3b',
        'choices': [{'index': 0, 'message': message, 'finish_reason': 'tool_calls'}],
    }


def openai_call(arguments: str, call_id: str = 'call_9') -> dict[str, Any]:
    return {
        'id': call_id,
        'type': 'function',
        'function': {'name': 'list_applications', 'arguments': arguments},
    }


def test_openai_sends_tools_and_the_tool_loop_history() -> None:
    requests: list[httpx2.Request] = []
    provider = recording(make_openai, requests, completion('You have one interview.'))
    turn = provider.chat_tools(HISTORY, TOOLS)

    assert turn == ToolTurn(text='You have one interview.', tool_calls=[], raw=turn.raw)
    body = body_of(requests[0])
    assert body['tools'] == [
        {
            'type': 'function',
            'function': {
                'name': 'list_applications',
                'description': 'List your applications.',
                'parameters': TOOLS[0].parameters,
            },
        }
    ]
    assistant, result = body['messages'][2], body['messages'][3]
    assert assistant['role'] == 'assistant'
    assert assistant['tool_calls'][0]['id'] == 'call_1'
    assert json.loads(assistant['tool_calls'][0]['function']['arguments']) == {
        'status': 'interview'
    }
    assert result == {'role': 'tool', 'tool_call_id': 'call_1', 'content': '[{"id": 3}]'}


def test_openai_reads_tool_calls() -> None:
    requests: list[httpx2.Request] = []
    body = completion(None, [openai_call('{"status": "applied"}')])
    turn = recording(make_openai, requests, body).chat_tools(HISTORY, TOOLS)
    assert turn.text == ''
    assert turn.tool_calls == [
        ToolCall(id='call_9', name='list_applications', arguments={'status': 'applied'})
    ]


SIGNATURE = {'google': {'thought_signature': 'c2lnbmF0dXJl'}}


def test_openai_keeps_geminis_thought_signature_and_sends_it_back() -> None:
    """Gemini refuses a tool call sent back without its signature (HTTP 400)."""
    requests: list[httpx2.Request] = []
    call = {**openai_call('{}'), 'extra_content': SIGNATURE}
    provider = recording(make_openai, requests, completion(None, [call]))
    provider.name = 'gemini'

    turn = provider.chat_tools(HISTORY, TOOLS)
    assert turn.tool_calls[0].extra == SIGNATURE

    provider.chat_tools([*HISTORY, turn, ToolResult('call_9', '[]')], TOOLS)
    sent = body_of(requests[1])['messages'][4]['tool_calls'][0]
    assert sent['extra_content'] == SIGNATURE


def test_gemini_gets_a_stand_in_signature_for_calls_without_one() -> None:
    """Calls stored before signatures were kept, or made by another model in the chat."""
    requests: list[httpx2.Request] = []
    two = ToolTurn(text='', tool_calls=[CALL, ToolCall('call_2', 'list_applications', {})])
    history = [*HISTORY[:2], two, ToolResult('call_1', '[]'), ToolResult('call_2', '[]')]
    provider = recording(make_openai, requests, completion('Done.'))
    provider.name = 'gemini'

    provider.chat_tools(history, TOOLS)

    calls = body_of(requests[0])['messages'][2]['tool_calls']
    assert calls[0]['extra_content'] == SKIP_SIGNATURE
    assert 'extra_content' not in calls[1]


def test_other_providers_get_no_signature() -> None:
    requests: list[httpx2.Request] = []
    recording(make_openai, requests, completion('Done.')).chat_tools(HISTORY, TOOLS)
    assert 'extra_content' not in body_of(requests[0])['messages'][2]['tool_calls'][0]


def test_openai_empty_arguments_are_an_empty_object() -> None:
    requests: list[httpx2.Request] = []
    body = completion(None, [openai_call('')])
    turn = recording(make_openai, requests, body).chat_tools(HISTORY, TOOLS)
    assert turn.tool_calls[0].arguments == {}


@pytest.mark.parametrize('arguments', ['{"status": ', '["applied"]'])
def test_openai_broken_arguments_raise(arguments: str) -> None:
    requests: list[httpx2.Request] = []
    provider = recording(make_openai, requests, completion(None, [openai_call(arguments)]))
    with pytest.raises(AIProviderError, match='arguments'):
        provider.chat_tools(HISTORY, TOOLS)


def test_openai_empty_answer_raises() -> None:
    requests: list[httpx2.Request] = []
    provider = recording(make_openai, requests, completion('  '))
    with pytest.raises(AIProviderError, match='empty'):
        provider.chat_tools(HISTORY, TOOLS)


def test_openai_http_error_raises() -> None:
    provider = make_openai(lambda _r: httpx2.Response(500, json={'error': 'x'}))
    with pytest.raises(AIProviderError, match='500'):
        provider.chat_tools(HISTORY, TOOLS)


# --- Anthropic ------------------------------------------------------------------------------


def tool_use(call_id: str = 'toolu_1', arguments: Any = None) -> dict[str, Any]:
    return {
        'type': 'tool_use',
        'id': call_id,
        'name': 'list_applications',
        'input': arguments if arguments is not None else {'status': 'interview'},
    }


def test_anthropic_sends_tools_and_the_tool_loop_history() -> None:
    requests: list[httpx2.Request] = []
    provider = recording(make_anthropic, requests, message(THINKING, text('One interview.')))
    turn = provider.chat_tools(HISTORY, TOOLS)

    assert turn.text == 'One interview.'
    assert turn.tool_calls == []
    body = sent_anthropic(requests[0])
    assert body['system'] == 'You help a job seeker.'
    assert body['tools'] == [
        {
            'name': 'list_applications',
            'description': 'List your applications.',
            'input_schema': TOOLS[0].parameters,
        }
    ]
    assert body['messages'][1] == {
        'role': 'assistant',
        'content': [
            {
                'type': 'tool_use',
                'id': 'call_1',
                'name': 'list_applications',
                'input': {'status': 'interview'},
            }
        ],
    }
    assert body['messages'][2] == {
        'role': 'user',
        'content': [
            {
                'type': 'tool_result',
                'tool_use_id': 'call_1',
                'content': '[{"id": 3}]',
                'is_error': False,
            }
        ],
    }


def test_anthropic_reads_tool_calls() -> None:
    requests: list[httpx2.Request] = []
    body = message(THINKING, text('Let me look.'), tool_use(), stop_reason='tool_use')
    turn = recording(make_anthropic, requests, body).chat_tools(HISTORY, TOOLS)
    assert turn.text == 'Let me look.'
    assert turn.tool_calls == [
        ToolCall(id='toolu_1', name='list_applications', arguments={'status': 'interview'})
    ]


def test_anthropic_sends_its_own_turn_back_with_the_thinking_block() -> None:
    requests: list[httpx2.Request] = []
    first = message(THINKING, tool_use(), stop_reason='tool_use')
    provider = recording(make_anthropic, requests, first)
    turn = provider.chat_tools(HISTORY[:2], TOOLS)

    history = [*HISTORY[:2], turn, ToolResult(call_id='toolu_1', content='[]')]
    provider.chat_tools(history, TOOLS)

    sent_turn = sent_anthropic(requests[1])['messages'][1]
    assert [block['type'] for block in sent_turn['content']] == ['thinking', 'tool_use']
    assert sent_turn['content'][0]['signature'] == 'sig'


def test_anthropic_results_in_a_row_go_in_one_user_message() -> None:
    requests: list[httpx2.Request] = []
    provider = recording(make_anthropic, requests, message(text('Done.')))
    two_calls = ToolTurn(tool_calls=[CALL, ToolCall(id='call_2', name='x', arguments={})])
    provider.chat_tools(
        [
            ChatMessage(role='user', content='Hi'),
            two_calls,
            ToolResult(call_id='call_1', content='a'),
            ToolResult(call_id='call_2', content='b', is_error=True),
        ],
        TOOLS,
    )
    messages = sent_anthropic(requests[0])['messages']
    assert len(messages) == 3
    assert [block['tool_use_id'] for block in messages[2]['content']] == ['call_1', 'call_2']
    assert messages[2]['content'][1]['is_error'] is True


@pytest.mark.parametrize(
    ('body', 'error'),
    [
        (message(THINKING), 'empty'),
        (message(text('x'), stop_reason='refusal'), 'declined'),
        (message(text('x'), stop_reason='max_tokens'), 'before finishing'),
    ],
)
def test_anthropic_answers_we_cannot_use_raise(body: dict[str, Any], error: str) -> None:
    requests: list[httpx2.Request] = []
    with pytest.raises(AIProviderError, match=error):
        recording(make_anthropic, requests, body).chat_tools(HISTORY, TOOLS)
