import pytest
from pydantic import SecretStr

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.fake import FakeAIProvider
from app.ai.openai_compat import OpenAICompatProvider
from app.ai.registry import build_provider

SETTINGS = 'app.ai.registry.settings'


@pytest.fixture(autouse=True)
def default_ai_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Known settings for every test here, whatever the local .env says."""
    monkeypatch.setattr(f'{SETTINGS}.ai_model', 'qwen2.5:3b')
    monkeypatch.setattr(f'{SETTINGS}.ai_base_url', None)
    monkeypatch.setattr(f'{SETTINGS}.ai_timeout_seconds', 300)


def test_fake_needs_nothing() -> None:
    provider = build_provider('fake')
    assert isinstance(provider, FakeAIProvider)
    assert provider.base_url is None


def test_ollama_uses_the_local_address_and_settings() -> None:
    provider = build_provider('ollama')

    assert isinstance(provider, OpenAICompatProvider)
    assert provider.name == 'ollama'
    assert provider.model == 'qwen2.5:3b'
    assert provider.base_url == 'http://localhost:11434/v1'
    assert provider.client.timeout == 300
    assert provider.client.max_retries == 0


def test_base_url_setting_replaces_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f'{SETTINGS}.ai_base_url', 'http://ollama:11434/v1')
    assert build_provider('ollama').base_url == 'http://ollama:11434/v1'


def test_gemini_uses_its_key_and_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f'{SETTINGS}.gemini_api_key', SecretStr('gem-key'))
    monkeypatch.setattr(f'{SETTINGS}.ai_model', 'gemini-2.5-flash')

    provider = build_provider('gemini')

    assert isinstance(provider, OpenAICompatProvider)
    assert provider.base_url == 'https://generativelanguage.googleapis.com/v1beta/openai/'
    assert provider.client.api_key == 'gem-key'
    assert provider.model == 'gemini-2.5-flash'


def test_openai_uses_its_key_and_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f'{SETTINGS}.openai_api_key', SecretStr('sk-test'))

    provider = build_provider('openai')

    assert isinstance(provider, OpenAICompatProvider)
    assert provider.base_url == 'https://api.openai.com/v1'
    assert provider.client.api_key == 'sk-test'


def test_anthropic_uses_its_key_and_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f'{SETTINGS}.anthropic_api_key', SecretStr('sk-ant-test'))
    monkeypatch.setattr(f'{SETTINGS}.ai_model', 'claude-opus-5-5')

    provider = build_provider('anthropic')

    assert isinstance(provider, AnthropicProvider)
    assert (provider.name, provider.model) == ('anthropic', 'claude-opus-5-5')
    assert provider.base_url is None  # the package's own address
    assert provider.client.api_key == 'sk-ant-test'
    assert provider.client.timeout == 300


@pytest.mark.parametrize(
    ('name', 'setting', 'env_name'),
    [
        ('openai', 'openai_api_key', 'OPENAI_API_KEY'),
        ('gemini', 'gemini_api_key', 'GEMINI_API_KEY'),
        ('anthropic', 'anthropic_api_key', 'ANTHROPIC_API_KEY'),
    ],
)
@pytest.mark.parametrize('key', [None, SecretStr(''), SecretStr('   ')])
def test_cloud_provider_without_key_fails_naming_the_setting(
    monkeypatch: pytest.MonkeyPatch, name: str, setting: str, env_name: str, key: SecretStr | None
) -> None:
    monkeypatch.setattr(f'{SETTINGS}.{setting}', key)
    with pytest.raises(ValueError, match=f'{env_name} is empty'):
        build_provider(name)


def test_unknown_name_fails_naming_the_setting() -> None:
    with pytest.raises(
        ValueError, match='Unknown AI provider in AI_PROVIDER: olama. Known: fake, ollama, openai'
    ):
        build_provider('olama')
