from collections.abc import Callable

from pydantic import SecretStr

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base import AIProvider
from app.ai.fake import FakeAIProvider
from app.ai.openai_compat import MAX_ANSWER_TOKENS, OpenAICompatProvider
from app.core.config import settings

# Where each provider's OpenAI-compatible API lives; AI_BASE_URL replaces it when set
DEFAULT_BASE_URLS = {
    'ollama': 'http://localhost:11434/v1',
    'openai': 'https://api.openai.com/v1',
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai/',
}


def require_key(key: SecretStr | None, env_name: str) -> str:
    """The API key's value; raise ValueError at startup if the provider is on but has no key."""
    if key is None or not key.get_secret_value().strip():
        raise ValueError(f'{env_name} is empty, but AI_PROVIDER turns this provider on.')
    return key.get_secret_value()


def build_openai_compat(name: str, api_key: str) -> AIProvider:
    return OpenAICompatProvider(
        name=name,
        base_url=settings.ai_base_url or DEFAULT_BASE_URLS[name],
        api_key=api_key,
        model=settings.ai_model,
        timeout=settings.ai_timeout_seconds,
        max_tokens=MAX_ANSWER_TOKENS if name == 'ollama' else None,
        max_retries=0 if name == 'ollama' else 3,
    )


def build_anthropic() -> AIProvider:
    return AnthropicProvider(
        api_key=require_key(settings.anthropic_api_key, 'ANTHROPIC_API_KEY'),
        model=settings.ai_model,
        timeout=settings.ai_timeout_seconds,
        base_url=settings.ai_base_url,  # None = Anthropic's own address
    )


# Name in settings -> function that builds the provider
PROVIDER_FACTORIES: dict[str, Callable[[], AIProvider]] = {
    'fake': FakeAIProvider,
    # Ollama ignores the key, but the openai package refuses to start without one
    'ollama': lambda: build_openai_compat('ollama', 'ollama'),
    'openai': lambda: build_openai_compat(
        'openai', require_key(settings.openai_api_key, 'OPENAI_API_KEY')
    ),
    'gemini': lambda: build_openai_compat(
        'gemini', require_key(settings.gemini_api_key, 'GEMINI_API_KEY')
    ),
    'anthropic': build_anthropic,
}


def build_provider(name: str) -> AIProvider:
    """Build the provider named in settings; raise ValueError for a name we don't know."""
    if name not in PROVIDER_FACTORIES:
        raise ValueError(
            f'Unknown AI provider in AI_PROVIDER: {name}. Known: {", ".join(PROVIDER_FACTORIES)}'
        )
    return PROVIDER_FACTORIES[name]()
