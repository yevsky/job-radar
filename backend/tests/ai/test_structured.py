import pytest
from pydantic import BaseModel, Field

from app.ai.base import AIProviderError, ChatMessage
from app.ai.fake import FakeAIProvider
from app.ai.structured import AIOutputError, extract_json, generate


class Skills(BaseModel):
    skills: list[str]
    score: int = Field(ge=0, le=100)


MESSAGES = [
    ChatMessage(role='system', content='Answer only with JSON.'),
    ChatMessage(role='user', content='We need a Python developer.'),
]
VALID = '{"skills": ["Python"], "score": 80}'
EXPECTED = Skills(skills=['Python'], score=80)


# extract_json


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('{"a": 1}', '{"a": 1}'),
        ('```json\n{"a": 1}\n```', '{"a": 1}'),
        ('Sure! Here it is: {"a": {"b": 2}} Hope it helps.', '{"a": {"b": 2}}'),
        ('no json here', None),
        ('} backwards {', None),
        ('', None),
    ],
)
def test_extract_json(text: str, expected: str | None) -> None:
    assert extract_json(text) == expected


# generate: first answer is fine


def test_valid_answer_is_returned_after_one_call() -> None:
    provider = FakeAIProvider(responses=[VALID])
    assert generate(provider, MESSAGES, Skills) == EXPECTED
    assert provider.calls == [MESSAGES]


@pytest.mark.parametrize(
    'answer',
    [
        f'```json\n{VALID}\n```',
        f'Here is the JSON you asked for:\n{VALID}',
        f'{VALID}\nLet me know if you need anything else.',
    ],
)
def test_text_around_the_json_is_ignored(answer: str) -> None:
    provider = FakeAIProvider(responses=[answer])
    assert generate(provider, MESSAGES, Skills) == EXPECTED
    assert len(provider.calls) == 1


# generate: one retry


def test_invalid_then_valid_asks_again_with_the_error() -> None:
    bad = '{"skills": ["Python"], "score": 150}'
    provider = FakeAIProvider(responses=[bad, VALID])

    assert generate(provider, MESSAGES, Skills) == EXPECTED

    assert len(provider.calls) == 2
    retry = provider.calls[1]
    assert retry[:2] == MESSAGES  # the original question is sent again
    assert retry[2] == ChatMessage(role='assistant', content=bad)  # its own bad answer
    assert retry[3].role == 'user'
    assert 'score: Input should be less than or equal to 100' in retry[3].content


def test_missing_field_is_named_in_the_retry() -> None:
    provider = FakeAIProvider(responses=['{"score": 50}', VALID])
    generate(provider, MESSAGES, Skills)
    assert 'skills: Field required' in provider.calls[1][3].content


def test_answer_without_json_is_retried() -> None:
    provider = FakeAIProvider(responses=['Sorry, I cannot help with that.', VALID])
    assert generate(provider, MESSAGES, Skills) == EXPECTED
    assert 'no JSON object' in provider.calls[1][3].content


def test_broken_json_is_retried() -> None:
    provider = FakeAIProvider(responses=['{"skills": ["Python", "score": 80}', VALID])
    assert generate(provider, MESSAGES, Skills) == EXPECTED
    # broken JSON is not about one field, so the error is named 'answer'
    assert 'answer: Invalid JSON' in provider.calls[1][3].content


def test_callers_messages_are_not_changed() -> None:
    messages = list(MESSAGES)
    provider = FakeAIProvider(responses=['{}', VALID])
    generate(provider, messages, Skills)
    assert messages == MESSAGES


# generate: gives up


def test_invalid_twice_raises_with_both_errors_and_no_third_call() -> None:
    provider = FakeAIProvider(responses=['{"score": 150}', 'still not JSON'])

    with pytest.raises(AIOutputError) as caught:
        generate(provider, MESSAGES, Skills)

    assert len(provider.calls) == 2
    first, second = caught.value.errors
    assert 'skills: Field required' in first
    assert 'score: Input should be less than or equal to 100' in first
    assert 'no JSON object' in second


def test_provider_error_is_passed_up_without_retry() -> None:
    provider = FakeAIProvider(fail=True)
    with pytest.raises(AIProviderError):
        generate(provider, MESSAGES, Skills)
    assert len(provider.calls) == 1


def test_wrong_type_is_named_in_the_retry() -> None:
    provider = FakeAIProvider(responses=['{"skills": "Python", "score": 80}', VALID])
    generate(provider, MESSAGES, Skills)
    assert 'skills: Input should be a valid array' in provider.calls[1][3].content
