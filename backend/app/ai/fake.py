from typing import override

from app.ai.base import AIProvider, AIProviderError, ChatMessage


class FakeAIProvider(AIProvider):
    """An AI provider with canned answers, for tests and for working without a model.

    Answers come out in the given order; once they run out, the last one repeats.
    So FakeAIProvider(['not json', '{"ok": true}']) fails once and then succeeds.
    """

    name = 'fake'
    model = 'fake'

    def __init__(self, responses: list[str] | None = None, fail: bool = False) -> None:
        self.responses = responses or ['{}']
        self.fail = fail
        self.calls: list[list[ChatMessage]] = []  # the messages of every call, for tests

    @override
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        self.calls.append(list(messages))
        if self.fail:
            raise AIProviderError('fake provider is set to fail')
        index = min(len(self.calls), len(self.responses)) - 1
        return self.responses[index]

    @override
    def test(self) -> bool:
        return not self.fail
