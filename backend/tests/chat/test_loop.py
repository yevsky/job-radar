"""The tool loop: text answers, read tools, history, limits and provider errors."""

from fastapi import status
from fastapi.testclient import TestClient

from app.ai.base import ChatMessage, ToolCall, ToolResult, ToolTurn
from app.ai.fake import FakeAIProvider
from app.schemas.chat import MAX_MESSAGE_CHARS
from app.services.chat import MAX_STEPS, STEP_LIMIT_TEXT
from tests.chat.conftest import Headers, Script, call, say, send
from tests.conftest import UseProvider


def test_a_text_answer(api: TestClient, headers: Headers, chat_id: int, script: Script) -> None:
    fake = script(say('Hello! How can I help?'))
    body = send(api, headers, chat_id, 'Hi')

    assert [(m['role'], m['content']) for m in body['messages']] == [
        ('user', 'Hi'),
        ('assistant', 'Hello! How can I help?'),
    ]
    assert body['pending_actions'] == []
    system, user = fake.tool_calls[0]
    assert isinstance(system, ChatMessage)
    assert system.role == 'system'
    assert 'untrusted' in system.content
    assert user == ChatMessage(role='user', content='Hi')


def test_every_tool_is_offered(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    fake = script(say('Hi'))
    send(api, headers, chat_id, 'Hi')
    names = {spec.name for spec in fake.tool_specs[0]}
    assert {'get_profile', 'search_jobs', 'save_offer', 'set_application_status'} <= names
    assert 'add_offer_from_text' in names
    for spec in fake.tool_specs[0]:
        assert '$defs' not in str(spec.parameters)  # flat schemas for small models
        assert 'draft' not in str(spec.parameters)  # filled by the app, never by the model


def test_a_read_tool_runs_and_its_result_goes_back(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    fake = script(call('get_profile'), say('You want a junior Python job.'))
    body = send(api, headers, chat_id, 'What do I want?')

    assert [m['role'] for m in body['messages']] == ['user', 'tool', 'assistant']
    assert body['messages'][1]['tool_name'] == 'get_profile'
    assert body['messages'][1]['content'] == 'Read your profile'
    second = fake.tool_calls[1]
    assert isinstance(second[-2], ToolTurn)
    result = second[-1]
    assert isinstance(result, ToolResult)
    assert result.call_id == 'call_1'
    assert '"skills"' in result.content
    assert 'first_name' not in result.content  # personal fields never go to the model


def test_earlier_tool_calls_are_part_of_the_next_history(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(turns=[call('get_profile'), say('Done.')]))
    send(api, headers, chat_id, 'First')
    fake = FakeAIProvider(turns=[say('Again.')])
    use_provider(fake)
    send(api, headers, chat_id, 'Second')

    history = fake.tool_calls[0][1:]  # without the system message
    assert history[0] == ChatMessage(role='user', content='First')
    assert history[1] == ToolTurn(
        tool_calls=[ToolCall(id='call_1', name='get_profile', arguments={})]
    )
    assert isinstance(history[2], ToolResult)
    assert history[3] == ChatMessage(role='assistant', content='Done.')
    assert history[4] == ChatMessage(role='user', content='Second')


def test_a_calls_provider_data_is_stored_and_sent_back_later(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    """Gemini's thought signature must come back with the call in the next messages too."""
    signature = {'google': {'thought_signature': 'abc'}}
    signed = ToolTurn(tool_calls=[ToolCall('call_1', 'get_profile', {}, signature)])
    use_provider(FakeAIProvider(turns=[signed, say('Done.')]))
    send(api, headers, chat_id, 'First')
    fake = FakeAIProvider(turns=[say('Again.')])
    use_provider(fake)
    send(api, headers, chat_id, 'Second')

    replayed = fake.tool_calls[0][2]
    assert isinstance(replayed, ToolTurn)
    assert replayed.tool_calls[0].extra == signature


def test_an_unknown_tool_is_an_error_result(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    fake = script(call('delete_everything'), say('I cannot do that.'))
    body = send(api, headers, chat_id, 'Delete everything')
    result = fake.tool_calls[1][-1]
    assert isinstance(result, ToolResult)
    assert result.is_error
    assert 'no tool called delete_everything' in result.content
    assert body['messages'][-1]['content'] == 'I cannot do that.'


def test_wrong_arguments_are_an_error_result(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    fake = script(call('get_job_offer', offer_id='abc'), say('Sorry.'))
    send(api, headers, chat_id, 'Show offer abc')
    result = fake.tool_calls[1][-1]
    assert isinstance(result, ToolResult)
    assert result.is_error
    assert 'offer_id' in result.content


def test_the_loop_stops_after_the_step_limit(
    api: TestClient, headers: Headers, chat_id: int, script: Script
) -> None:
    fake = script(call('get_profile'))  # calls a tool forever
    body = send(api, headers, chat_id, 'Loop')
    assert len(fake.tool_calls) == MAX_STEPS
    assert body['messages'][-1]['content'] == STEP_LIMIT_TEXT


def test_a_provider_error_is_502_and_the_message_is_kept(
    api: TestClient, headers: Headers, chat_id: int, use_provider: UseProvider
) -> None:
    use_provider(FakeAIProvider(fail=True))
    response = api.post(f'/chat/{chat_id}/messages', json={'content': 'Hi'}, headers=headers)
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    # the reason is shown, so a wrong model name or key is easy to spot
    assert response.json()['detail'].endswith('fake provider is set to fail')
    messages = api.get(f'/chat/{chat_id}', headers=headers).json()['messages']
    assert [m['content'] for m in messages] == ['Hi']


def test_message_length_is_checked(api: TestClient, headers: Headers, chat_id: int) -> None:
    for content in ['', '   ', 'x' * (MAX_MESSAGE_CHARS + 1)]:
        response = api.post(f'/chat/{chat_id}/messages', json={'content': content}, headers=headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
