from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    PRODUCTION = "production"


class BotMode(StrEnum):
    POLLING = "polling"
    WEBHOOK = "webhook"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://fenix:fenix@localhost:5432/fenix"
    redis_url: str = "redis://localhost:6379/0"

    telegram_bot_token: SecretStr
    telegram_bot_mode: BotMode = BotMode.POLLING
    # Base public URL of the deployment, e.g. https://fenix.example.ru.
    # The webhook is registered at {public_base_url}/telegram/webhook.
    public_base_url: str | None = None
    telegram_webhook_secret: SecretStr | None = None
    # Where the Mini App is served. Telegram requires HTTPS outside its test environment.
    webapp_url: str | None = None
    # Outbound proxy for the Bot API (http://, socks5://). Needed where Telegram is blocked.
    telegram_proxy_url: SecretStr | None = None

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
