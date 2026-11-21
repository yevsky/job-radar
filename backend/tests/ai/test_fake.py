import pytest

from app.ai.base import AIProvider, AIProviderError, ChatMessage
from app.ai.fake import FakeAIProvider

MESSAGES = [
    ChatMessage(role='system', content='Answer only with JSON.'),
    ChatMessage(role='user', content='We need a Python developer.'),
]


def test_returns_responses_in_order() -> None:
    provider = FakeAIProvider(responses=['first', 'second'])
    assert provider.chat(MESSAGES) == 'first'
    assert provider.chat(MESSAGES) == 'second'


def test_repeats_the_last_response_when_the_queue_is_empty() -> None:
    provider = FakeAIProvider(responses=['first', 'last'])
    answers = [provider.chat(MESSAGES) for _ in range(4)]
    assert answers == ['first', 'last', 'last', 'last']


def test_without_responses_returns_an_empty_json_object() -> None:
    assert FakeAIProvider().chat(MESSAGES) == '{}'


def test_records_the_messages_of_every_call() -> None:
    provider = FakeAIProvider()
    other = [ChatMessage(role='user', content='Hi')]
    provider.chat(MESSAGES)
    provider.chat(other, json_mode=False)
    assert provider.calls == [MESSAGES, other]


def test_recorded_messages_dont_change_when_the_caller_changes_its_list() -> None:
    provider = FakeAIProvider()
    messages = list(MESSAGES)
    provider.chat(messages)
    messages.append(ChatMessage(role='user', content='One more'))
    assert provider.calls == [MESSAGES]


def test_failing_fake_raises_and_still_records_the_call() -> None:
    provider = FakeAIProvider(responses=['never returned'], fail=True)
    with pytest.raises(AIProviderError):
        provider.chat(MESSAGES)
    assert provider.calls == [MESSAGES]


def test_test_method_reports_health() -> None:
    assert FakeAIProvider().test() is True
    assert FakeAIProvider(fail=True).test() is False


def test_name_and_model_are_fake() -> None:
    provider = FakeAIProvider()
    assert provider.name == 'fake'
    assert provider.model == 'fake'


def test_fake_is_an_ai_provider() -> None:
    provider: AIProvider = FakeAIProvider()  # mypy checks this line too
    assert isinstance(provider, AIProvider)


def test_interface_cannot_be_used_directly() -> None:
    with pytest.raises(TypeError):
        AIProvider()  # type: ignore[abstract]


def test_chat_message_is_compared_by_value_and_cannot_be_changed() -> None:
    message = ChatMessage(role='user', content='Hi')
    assert message == ChatMessage(role='user', content='Hi')
    with pytest.raises(AttributeError):
        message.content = 'Changed'  # type: ignore[misc]
