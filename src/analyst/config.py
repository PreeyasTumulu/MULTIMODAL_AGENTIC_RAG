"""Application settings, loaded from environment / .env.

One source of truth. Nothing in this project reads os.environ directly.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- database
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_user: str = "analyst"
    postgres_password: SecretStr = SecretStr("analyst")
    postgres_db: str = "analyst"

    # --- vector store
    qdrant_url: str = "http://localhost:6333"
    collection_prefix: str = "elements"

    # --- llm providers (wired on Day 5)
    groq_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"

    # --- paths / misc
    data_dir: Path = Path("data")
    log_level: str = "INFO"

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL.

        Deliberately a plain property, NOT a pydantic computed_field: a computed
        field is included in model_dump()/logging, which would leak the password.
        """
        pwd = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{pwd}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so .env is parsed once per process."""
    return Settings()
