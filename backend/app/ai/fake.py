from typing import override

from app.ai.base import (
    AIProvider,
    AIProviderError,
    ChatMessage,
    ToolMessage,
    ToolSpec,
    ToolTurn,
)


class FakeAIProvider(AIProvider):
    """An AI provider with canned answers, for tests and for working without a model.

    Answers come out in the given order; once they run out, the last one repeats.
    So FakeAIProvider(['not json', '{"ok": true}']) fails once and then succeeds.
    Tool loops work the same way with `turns`: a scripted list of ToolTurns.
    """

    name = 'fake'
    model = 'fake'

    def __init__(
        self,
        responses: list[str] | None = None,
        fail: bool = False,
        turns: list[ToolTurn] | None = None,
    ) -> None:
        self.responses = responses or ['{}']
        self.fail = fail
        self.turns = turns or [ToolTurn(text='This is a fake answer.')]
        self.calls: list[list[ChatMessage]] = []  # the messages of every call, for tests
        self.tool_calls: list[list[ToolMessage]] = []  # the history of every chat_tools call
        self.tool_specs: list[list[ToolSpec]] = []  # the tools offered in every chat_tools call

    @override
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        self.calls.append(list(messages))
        if self.fail:
            raise AIProviderError('fake provider is set to fail')
        index = min(len(self.calls), len(self.responses)) - 1
        return self.responses[index]

    @override
    def chat_tools(self, messages: list[ToolMessage], tools: list[ToolSpec]) -> ToolTurn:
        self.tool_calls.append(list(messages))
        self.tool_specs.append(list(tools))
        if self.fail:
            raise AIProviderError('fake provider is set to fail')
        index = min(len(self.tool_calls), len(self.turns)) - 1
        return self.turns[index]

    @override
    def test(self) -> bool:
        return not self.fail
