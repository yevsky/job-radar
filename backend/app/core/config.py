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

    model_config = SettingsConfigDict(
        env_file=[
            BASE_DIR / '.env',
        ],
        env_file_encoding='utf-8',
    )


settings = Settings()  # type: ignore[call-arg]
