from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FM_",
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    env: Literal["production", "development", "test"] = "production"
    data_dir: Path = BACKEND_DIR / "data"
    database_url: str | None = None
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"
    cors_origins: list[str] = []
    cookie_secure: Literal["auto", "true", "false"] = "auto"
    session_days: int = 30
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @property
    def is_dev(self) -> bool:
        return self.env == "development"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.data_dir / 'finanzmanager.db').as_posix()}"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"


@lru_cache
def get_settings() -> Settings:
    return Settings()
