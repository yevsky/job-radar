"""The AI provider interface: what every AI backend (Ollama, OpenAI, Gemini, a fake) offers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Role = Literal['system', 'user', 'assistant']


class AIProviderError(Exception):
    """An AI call failed: timeout, connection refused, wrong key, or an empty answer."""


@dataclass(frozen=True)
class ChatMessage:
    """One message of a chat: the rules (system), the question (user) or an earlier answer."""

    role: Role
    content: str


class AIProvider(ABC):
    """One AI backend. Messages go in, the model's answer comes out as plain text.

    Providers know nothing about our schemas: turning the text into a Pydantic model
    (and retrying on bad output) happens once, above them, in app/ai/structured.py.
    """

    name: str  # short id saved with every result, e.g. 'ollama'
    model: str  # e.g. 'qwen2.5:3b'

    @abstractmethod
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        """Send the messages and return the answer text; raise AIProviderError on failure.

        json_mode asks the backend to answer with a JSON object only.
        """

    @abstractmethod
    def test(self) -> bool:
        """Return True if the provider answers (server up, key valid). Never raises."""
