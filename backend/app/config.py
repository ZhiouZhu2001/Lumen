from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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
    daily_ai_call_cap: int = Field(default=100, ge=1)
    trusted_proxy_ips: list[str] = []

    @field_validator("trusted_proxy_ips")
    @classmethod
    def validate_proxies(cls, value):
        for network in value:
            if ip_network(network).prefixlen == 0:
                raise ValueError("Trust explicit proxies, not every client")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
