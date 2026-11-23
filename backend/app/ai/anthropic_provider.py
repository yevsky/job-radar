"""Claude through Anthropic's Messages API, behind the same AIProvider interface.

Anthropic's API isn't OpenAI-compatible: the system prompt is its own field, max_tokens is
required, there is no response_format and no temperature, and the answer is a list of
content blocks (thinking, text, ...) instead of one string.
"""

from typing import Any, Final, cast, override

import anthropic
import httpx2
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaToolParam,
    BetaToolResultBlockParam,
)

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

# Room for the model's (always on) thinking plus our small JSON answers
MAX_TOKENS = 16_000
# Our tasks are reading and filling a schema: little thinking needed, so faster and cheaper
EFFORT: Final = 'low'
# If a safety classifier declines a request, the API retries it on a recommended model.
# On models without fallbacks, 'default' just runs the request alone.
FALLBACK_BETA: Final = 'server-side-fallback-2026-07-01'
JSON_ONLY = 'Answer with one JSON object only: no text before or after it, no code fence.'


def split_system(messages: list[ChatMessage]) -> tuple[str, list[BetaMessageParam]]:
    """Anthropic takes the system prompt as a separate field, the rest as messages."""
    system = '\n\n'.join(m.content for m in messages if m.role == 'system')
    rest: list[BetaMessageParam] = []
    for message in messages:
        if message.role == 'user':
            rest.append({'role': 'user', 'content': message.content})
        elif message.role == 'assistant':
            rest.append({'role': 'assistant', 'content': message.content})
    return system, rest


# Blocks of an answer that go back unchanged while a tool loop goes on
KEPT_BLOCKS = ('thinking', 'redacted_thinking', 'text', 'tool_use')


def assistant_blocks(turn: ToolTurn) -> list[BetaContentBlockParam]:
    """The model's own tool turn, to send back: its raw blocks (thinking included) if we
    have them, else text and tool_use blocks built from the turn."""
    if isinstance(turn.raw, BetaMessage):
        return [
            cast(BetaContentBlockParam, block.model_dump(exclude_none=True))
            for block in turn.raw.content
            if block.type in KEPT_BLOCKS
        ]
    blocks: list[BetaContentBlockParam] = []
    if turn.text:
        blocks.append({'type': 'text', 'text': turn.text})
    for call in turn.tool_calls:
        blocks.append(
            {'type': 'tool_use', 'id': call.id, 'name': call.name, 'input': call.arguments}
        )
    return blocks


def split_tool_messages(messages: list[ToolMessage]) -> tuple[str, list[BetaMessageParam]]:
    """The system prompt and the messages of a tool loop in Anthropic's shape.

    Tool results that follow each other go into one user message, as the API asks.
    """
    system = '\n\n'.join(
        m.content for m in messages if isinstance(m, ChatMessage) and m.role == 'system'
    )
    rest: list[BetaMessageParam] = []
    results: list[BetaToolResultBlockParam] = []
    for message in messages:
        if isinstance(message, ToolResult):
            results.append(
                {
                    'type': 'tool_result',
                    'tool_use_id': message.call_id,
                    'content': message.content,
                    'is_error': message.is_error,
                }
            )
            continue
        if results:
            rest.append({'role': 'user', 'content': list(results)})
            results = []
        if isinstance(message, ToolTurn):
            rest.append({'role': 'assistant', 'content': assistant_blocks(message)})
        elif message.role == 'user':
            rest.append({'role': 'user', 'content': message.content})
        elif message.role == 'assistant':
            rest.append({'role': 'assistant', 'content': message.content})
    if results:
        rest.append({'role': 'user', 'content': list(results)})
    return system, rest


def tool_to_anthropic(tool: ToolSpec) -> BetaToolParam:
    return {
        'name': tool.name,
        'description': tool.description,
        'input_schema': cast(Any, tool.parameters),
    }


def answer_text(response: object, name: str) -> str:
    """The text blocks of the answer, joined; thinking and fallback blocks are skipped."""
    if not isinstance(response, BetaMessage):  # e.g. an HTML page from a proxy
        raise AIProviderError(f'{name} sent something that is not a message')
    if response.stop_reason == 'refusal':
        raise AIProviderError(f'{name} declined to answer')
    if response.stop_reason == 'max_tokens':
        raise AIProviderError(f'{name} stopped before finishing the answer')
    text = ''.join(block.text for block in response.content if block.type == 'text')
    if not text.strip():
        raise AIProviderError(f'{name} returned an empty answer')
    return text


class AnthropicProvider(AIProvider):
    """Claude models (e.g. claude-opus-5-5) through the official anthropic package."""

    name = 'anthropic'

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float,
        base_url: str | None = None,
        max_retries: int = 2,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            # The package retries 429 (rate limit), 529 (overloaded) and 5xx after a pause
            max_retries=max_retries,
            http_client=http_client,  # tests pass a client that never touches the network
        )

    @override
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        system, rest = split_system(messages)
        if json_mode:  # no response_format here; generate() validates the answer anyway
            system = f'{system}\n\n{JSON_ONLY}' if system else JSON_ONLY
        return answer_text(self._create(system, rest), self.name)

    @override
    def chat_tools(self, messages: list[ToolMessage], tools: list[ToolSpec]) -> ToolTurn:
        system, rest = split_tool_messages(messages)
        response = self._create(system, rest, [tool_to_anthropic(tool) for tool in tools])
        if not isinstance(response, BetaMessage):
            raise AIProviderError(f'{self.name} sent something that is not a message')
        if response.stop_reason == 'refusal':
            raise AIProviderError(f'{self.name} declined to answer')
        if response.stop_reason == 'max_tokens':
            raise AIProviderError(f'{self.name} stopped before finishing the answer')
        text = ''.join(block.text for block in response.content if block.type == 'text')
        calls = [
            ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
            for block in response.content
            if block.type == 'tool_use'
        ]
        if not text.strip() and not calls:
            raise AIProviderError(f'{self.name} returned an empty answer')
        return ToolTurn(text=text.strip(), tool_calls=calls, raw=response)

    def _create(
        self,
        system: str,
        messages: list[BetaMessageParam],
        tools: list[BetaToolParam] | None = None,
    ) -> object:
        """One Messages API call; every failure becomes AIProviderError."""
        try:
            return self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system or anthropic.omit,
                messages=messages,
                tools=tools or anthropic.omit,
                output_config={'effort': EFFORT},
                betas=[FALLBACK_BETA],
                fallbacks='default',
            )
        except anthropic.APITimeoutError as err:  # before APIConnectionError: it's a subclass
            raise AIProviderError(f'{self.name} did not answer in time') from err
        except anthropic.APIConnectionError as err:
            raise AIProviderError(f'Cannot reach {self.name}') from err
        except anthropic.APIStatusError as err:
            raise AIProviderError(f'{self.name} answered with HTTP {err.status_code}') from err
        except anthropic.AnthropicError as err:  # anything else the package can raise
            raise AIProviderError(f'{self.name} failed: {err}') from err

    @override
    def test(self) -> bool:
        """True if the key works and the model exists. Reads the model's info: no tokens used."""
        try:
            self.client.models.retrieve(self.model)
        except anthropic.AnthropicError:
            return False
        return True
