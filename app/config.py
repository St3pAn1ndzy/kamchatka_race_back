from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENV: str = "dev"
    DEBUG: bool = True
    SECRET_KEY: str = "change-me"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Логирование тел запросов при ошибках валидации (по умолчанию ВЫКЛЮЧЕНО).
    # Включать ТОЛЬКО при отладке Pydantic-ошибок на локалке, не в проде.
    LOG_VALIDATION_ERROR_BODY: bool = False

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "avacha"
    POSTGRES_PASSWORD: str = "avacha"
    POSTGRES_DB: str = "avacha"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Synchronous DSN for Alembic / SQLAdmin."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    VK_APP_ID: str = ""
    VK_SECURE_KEY: str = ""
    VK_SERVICE_TOKEN: str = ""
    VK_API_VERSION: str = "5.199"

    IRIDIUM_BASE_URL: str = "https://api.iridium360.ru"
    IRIDIUM_API_KEY: str = ""
    IRIDIUM_DEVICES_PATH: str = "/devices"
    IRIDIUM_REQUEST_TIMEOUT_SECONDS: float = 15.0
    IRIDIUM_MAX_RETRIES: int = 3
    IRIDIUM_RETRY_BACKOFF_SECONDS: float = 2.0
    TRACKING_POLL_INTERVAL_SECONDS: int = 900
    TRACKING_STALE_MISSED_INTERVALS: int = 2

    NOTIFICATION_RATE_LIMIT_PER_HOUR: int = 2
    NOTIFICATION_RATE_LIMIT_PER_DAY: int = 10

    ADMIN_SESSION_TTL_SECONDS: int = 28800  # 8h

    JWT_ALGORITHM: str = "HS256"
    JWT_USER_TTL_SECONDS: int = 86400  # 24h

    CORS_ORIGINS: str = "https://vk.com,https://m.vk.com,https://prod-apps.vkusercontent.com"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
