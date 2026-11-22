from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: SecretStr
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int
    # TODO: Delete None defaults for api keys
    gemini_api_key: SecretStr | None = None
    tavily_api_key: SecretStr | None = None
    jsearch_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # Which search sources POST /search asks, in this order. In .env as JSON:
    # SEARCH_SOURCES='["tavily","jsearch"]'. 'fake' returns demo results and needs no key.
    search_sources: list[str] = ['fake']
    search_results_per_source: int = 10
    # Job boards Tavily searches on. In .env as JSON: TAVILY_DOMAINS='["justjoin.it"]'
    tavily_domains: list[str] = ['justjoin.it', 'nofluffjobs.com', 'pracuj.pl', 'linkedin.com']
    # Country JSearch searches in (ISO code); it uses 'us' when none is sent
    jsearch_country: str = 'pl'
    # searches per user per day, unless an admin sets another
    search_daily_limit: int = 10

    # Which AI backend the app uses: fake | ollama | openai | gemini. 'fake' needs nothing.
    ai_provider: str = 'fake'
    ai_model: str = 'qwen2.5:3b'
    # Empty = the provider's usual address (Ollama: http://localhost:11434/v1)
    ai_base_url: str | None = None
    # A local model on a CPU can take minutes; cloud APIs answer in seconds
    ai_timeout_seconds: float = 300

    model_config = SettingsConfigDict(
        env_file=[
            BASE_DIR / '.env',
        ],
        env_file_encoding='utf-8',
    )


settings = Settings()  # type: ignore[call-arg]
