"""Claude through Anthropic's Messages API, behind the same AIProvider interface.

Anthropic's API isn't OpenAI-compatible: the system prompt is its own field, max_tokens is
required, there is no response_format and no temperature, and the answer is a list of
content blocks (thinking, text, ...) instead of one string.
"""

from typing import Final, override

import anthropic
import httpx2
from anthropic.types.beta import BetaMessage, BetaMessageParam

from app.ai.base import AIProvider, AIProviderError, ChatMessage

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
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system or anthropic.omit,
                messages=rest,
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
        return answer_text(response, self.name)

    @override
    def test(self) -> bool:
        """True if the key works and the model exists. Reads the model's info: no tokens used."""
        try:
            self.client.models.retrieve(self.model)
        except anthropic.AnthropicError:
            return False
        return True
