from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    api_base_url: AnyHttpUrl = "http://localhost:8000"
    cookie_secure: bool = False
    media_max_bytes: int = Field(default=512 * 1024 * 1024, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
