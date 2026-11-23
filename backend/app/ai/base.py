"""The AI provider interface: what every AI backend (Ollama, OpenAI, Gemini, a fake) offers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal['system', 'user', 'assistant']


class AIProviderError(Exception):
    """An AI call failed: timeout, connection refused, wrong key, or an empty answer."""


@dataclass(frozen=True)
class ChatMessage:
    """One message of a chat: the rules (system), the question (user) or an earlier answer."""

    role: Role
    content: str


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call: its name, what it does, and its arguments as a JSON schema."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """The model asks to run one tool. `id` links the call to its result."""

    id: str
    name: str
    arguments: dict[str, Any]
    # Provider data that must go back with the call, e.g. Gemini's thought signature
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class ToolTurn:
    """One answer of the model in a tool loop: text, tool calls, or both.

    `raw` is the provider's own answer object. Anthropic needs it sent back unchanged
    (with its thinking blocks) while the loop goes on; other providers ignore it.
    """

    text: str = ''
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: object = None


@dataclass(frozen=True)
class ToolResult:
    """What a tool returned, sent back to the model as the answer to one ToolCall."""

    call_id: str
    content: str
    is_error: bool = False


# A tool loop's history: plain messages, the model's tool turns and the tools' results
ToolMessage = ChatMessage | ToolTurn | ToolResult


class AIProvider(ABC):
    """One AI backend. Messages go in, the model's answer comes out as plain text.

    Providers know nothing about our schemas: turning the text into a Pydantic model
    (and retrying on bad output) happens once, above them, in app/ai/structured.py.
    """

    name: str  # short id saved with every result, e.g. 'ollama'
    model: str  # e.g. 'qwen2.5:3b'
    base_url: str | None = None  # where requests go; None for providers without a server

    @abstractmethod
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        """Send the messages and return the answer text; raise AIProviderError on failure.

        json_mode asks the backend to answer with a JSON object only.
        """

    @abstractmethod
    def test(self) -> bool:
        """Return True if the provider answers (server up, key valid). Never raises."""

    def chat_tools(self, messages: list[ToolMessage], tools: list[ToolSpec]) -> ToolTurn:  # noqa: ARG002
        """Send the history and the tools; return the model's text and/or tool calls.

        Raises AIProviderError on failure. Providers without tool support keep this default.
        """
        raise AIProviderError(f'{self.name} cannot call tools')
