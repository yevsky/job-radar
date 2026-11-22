"""One client for every AI backend that speaks the OpenAI chat format: Ollama, OpenAI, Gemini."""

from typing import override

import httpx2
import openai
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam

from app.ai.base import AIProvider, AIProviderError, ChatMessage


def to_openai(message: ChatMessage) -> ChatCompletionMessageParam:
    """Our ChatMessage in the shape the openai package expects."""
    match message.role:
        case 'system':
            return {'role': 'system', 'content': message.content}
        case 'user':
            return {'role': 'user', 'content': message.content}
        case 'assistant':
            return {'role': 'assistant', 'content': message.content}


class OpenAICompatProvider(AIProvider):
    """Talks to any OpenAI-compatible chat API; only base_url, api_key and model differ."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.base_url = base_url
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=0,  # one slow local call is enough
            http_client=http_client,  # tests pass a client that never touches the network
        )

    @override
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[to_openai(message) for message in messages],
                temperature=0,
                response_format={'type': 'json_object'} if json_mode else openai.omit,
            )
        except openai.APITimeoutError as err:  # before APIConnectionError: it's a subclass
            raise AIProviderError(f'{self.name} did not answer in time') from err
        except openai.APIConnectionError as err:
            raise AIProviderError(f'Cannot reach {self.name} at {self.base_url}') from err
        except openai.APIStatusError as err:
            raise AIProviderError(f'{self.name} answered with HTTP {err.status_code}') from err
        except openai.OpenAIError as err:  # anything else the package can raise
            raise AIProviderError(f'{self.name} failed: {err}') from err

        if not isinstance(response, ChatCompletion):  # e.g. an HTML page from a proxy
            raise AIProviderError(f'{self.name} sent something that is not a chat answer')
        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise AIProviderError(f'{self.name} returned an empty answer')
        return content

    @override
    def test(self) -> bool:
        """True if the server answers, the key works and the model is there.

        Asks for the model list instead of sending a prompt: it's free and quick, and it
        doesn't make Ollama load the model into memory.
        """
        try:
            ids = [model.id for model in self.client.models.list()]
        # OpenAIError: down, bad key, ...; the others: a body that isn't a model list
        except (openai.OpenAIError, AttributeError, TypeError, ValueError):
            return False
        # Gemini lists models as 'models/gemini-2.5-flash', the others as plain names
        return any(found in (self.model, f'models/{self.model}') for found in ids)
