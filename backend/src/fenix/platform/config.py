from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    PRODUCTION = "production"


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
    # Bot username without "@", for t.me deep links (staff invitations).
    telegram_bot_username: str | None = None
    # The first staff member: the Telegram user with this username who presses «Старт»
    # while the location has no staff yet. Set only in the server's .env.
    bootstrap_staff_telegram_username: str | None = None
    # Where the Mini App is served. Telegram requires HTTPS outside its test environment.
    webapp_url: str | None = None
    # Media storage (Garage, S3 API). Local defaults match infra/compose.dev.yaml.
    s3_endpoint_url: str = "http://localhost:3900"
    s3_bucket: str = "media"
    s3_access_key_id: str = "GK0123456789abcdef01234567"
    s3_secret_access_key: SecretStr = SecretStr("0" * 64)
    garage_admin_url: str = "http://localhost:3903"
    garage_admin_token: SecretStr = SecretStr("local-garage-admin-token")
    # Outbound proxy for the Bot API (http://, socks5://). Needed where Telegram is blocked.
    telegram_proxy_url: SecretStr | None = None

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
