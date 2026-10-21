from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")
    database_url: str
    redis_url: str
    sql_echo: bool = False
    google_books_api_key: str | None = None
    openai_api_key: SecretStr | None = None
    llm_model: str = "openai:gpt-5.4-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
