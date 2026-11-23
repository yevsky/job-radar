"""One client for every AI backend that speaks the OpenAI chat format: Ollama, OpenAI, Gemini."""

import json
from typing import Any, cast, override

import httpx2
import openai
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionFunctionToolParam,
    ChatCompletionMessageParam,
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


def to_openai(message: ChatMessage) -> ChatCompletionMessageParam:
    """Our ChatMessage in the shape the openai package expects."""
    match message.role:
        case 'system':
            return {'role': 'system', 'content': message.content}
        case 'user':
            return {'role': 'user', 'content': message.content}
        case 'assistant':
            return {'role': 'assistant', 'content': message.content}


# Gemini's documented stand-in for a thought signature we don't have: tool calls stored
# before signatures were kept, or made by another model earlier in the same chat.
SKIP_SIGNATURE = {'google': {'thought_signature': 'skip_thought_signature_validator'}}


def tool_message_to_openai(
    message: ToolMessage, needs_signature: bool = False
) -> ChatCompletionMessageParam:
    """One message of a tool loop in the OpenAI shape.

    Gemini (needs_signature) refuses a tool call sent back without the thought signature it
    came with (HTTP 400), so each call's `extra` goes back as `extra_content`.
    """
    if isinstance(message, ChatMessage):
        return to_openai(message)
    if isinstance(message, ToolResult):
        return {'role': 'tool', 'tool_call_id': message.call_id, 'content': message.content}
    calls: list[dict[str, Any]] = []
    for call in message.tool_calls:
        item: dict[str, Any] = {
            'id': call.id,
            'type': 'function',
            'function': {
                'name': call.name,
                'arguments': json.dumps(call.arguments, ensure_ascii=False),
            },
        }
        if call.extra:
            item['extra_content'] = call.extra
        calls.append(item)
    # Gemini checks the first call of each turn (in parallel calls only it has a signature)
    if needs_signature and calls and not any('extra_content' in c for c in calls):
        calls[0]['extra_content'] = SKIP_SIGNATURE
    return cast(
        ChatCompletionMessageParam,
        {'role': 'assistant', 'content': message.text or None, 'tool_calls': calls},
    )


def tool_to_openai(tool: ToolSpec) -> ChatCompletionFunctionToolParam:
    return {
        'type': 'function',
        'function': {
            'name': tool.name,
            'description': tool.description,
            'parameters': tool.parameters,
        },
    }


def read_arguments(name: str, text: str) -> dict[str, Any]:
    """Tool arguments come as a JSON string; small models sometimes break it."""
    try:
        arguments = json.loads(text or '{}')
    except json.JSONDecodeError as err:
        raise AIProviderError(f'The model sent broken arguments for {name}') from err
    if not isinstance(arguments, dict):
        raise AIProviderError(f'The model sent arguments for {name} that are not an object')
    return arguments


# The longest answer we wait for from a local model. A small model in JSON mode sometimes never
# stops (it repeats list entries or writes blank lines until the timeout); 2000 tokens is far
# more than any of our answers needs and takes about a minute on a small GPU. Cloud models get
# no limit: their thinking counts towards it and would cut the answer short.
MAX_ANSWER_TOKENS = 2000


def api_reason(err: openai.APIStatusError) -> str:
    """The message in the error body: {"error": {"message": ...}}, or the same inside a list
    (Gemini sends that, and the openai package then only says 'Error code: 400')."""
    body: object = err.body
    if isinstance(body, list) and body:
        body = body[0]
    if isinstance(body, dict):
        inner = body.get('error', body)
        if isinstance(inner, dict) and isinstance(inner.get('message'), str):
            return str(inner['message'])
    return err.message


def http_error(name: str, err: openai.APIStatusError) -> AIProviderError:
    """'gemini answered with HTTP 400: <the API's own reason>', cut short. The reason says
    what to fix (a model name, an unsupported field); the APIs never repeat the key in it."""
    reason = ' '.join(api_reason(err).split())[:300]
    return AIProviderError(f'{name} answered with HTTP {err.status_code}: {reason}')


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
        max_tokens: int | None = None,
        max_retries: int = 0,
    ) -> None:
        self.name = name
        self.max_tokens = max_tokens
        self.model = model
        self.base_url = base_url
        self.client = openai.OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            # Cloud APIs answer 429/503 when busy; the package then waits and asks again.
            # A slow local model gets one try: a retry would only double the wait.
            max_retries=max_retries,
            http_client=http_client,  # tests pass a client that never touches the network
        )

    @override
    def chat(self, messages: list[ChatMessage], json_mode: bool = True) -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[to_openai(message) for message in messages],
                temperature=0,
                max_tokens=self.max_tokens if self.max_tokens is not None else openai.omit,
                response_format={'type': 'json_object'} if json_mode else openai.omit,
            )
        except openai.APITimeoutError as err:  # before APIConnectionError: it's a subclass
            raise AIProviderError(f'{self.name} did not answer in time') from err
        except openai.APIConnectionError as err:
            raise AIProviderError(f'Cannot reach {self.name} at {self.base_url}') from err
        except openai.APIStatusError as err:
            raise http_error(self.name, err) from err
        except openai.OpenAIError as err:  # anything else the package can raise
            raise AIProviderError(f'{self.name} failed: {err}') from err

        if not isinstance(response, ChatCompletion):  # e.g. an HTML page from a proxy
            raise AIProviderError(f'{self.name} sent something that is not a chat answer')
        if response.choices and response.choices[0].finish_reason == 'length':
            raise AIProviderError(f'{self.name} stopped before finishing the answer')
        content = response.choices[0].message.content if response.choices else None
        if not content or not content.strip():
            raise AIProviderError(f'{self.name} returned an empty answer')
        return content

    @override
    def chat_tools(self, messages: list[ToolMessage], tools: list[ToolSpec]) -> ToolTurn:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    tool_message_to_openai(message, needs_signature=self.name == 'gemini')
                    for message in messages
                ],
                tools=[tool_to_openai(tool) for tool in tools] if tools else openai.omit,
                temperature=0,
            )
        except openai.APITimeoutError as err:
            raise AIProviderError(f'{self.name} did not answer in time') from err
        except openai.APIConnectionError as err:
            raise AIProviderError(f'Cannot reach {self.name} at {self.base_url}') from err
        except openai.APIStatusError as err:
            raise http_error(self.name, err) from err
        except openai.OpenAIError as err:
            raise AIProviderError(f'{self.name} failed: {err}') from err

        if not isinstance(response, ChatCompletion) or not response.choices:
            raise AIProviderError(f'{self.name} sent something that is not a chat answer')
        answer = response.choices[0].message
        calls = [
            ToolCall(
                id=call.id,
                name=call.function.name,
                arguments=read_arguments(call.function.name, call.function.arguments),
                extra=(call.model_extra or {}).get('extra_content'),
            )
            for call in answer.tool_calls or []
            if call.type == 'function'
        ]
        text = (answer.content or '').strip()
        if not text and not calls:
            raise AIProviderError(f'{self.name} returned an empty answer')
        return ToolTurn(text=text, tool_calls=calls, raw=response)

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
