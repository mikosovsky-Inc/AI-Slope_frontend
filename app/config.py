from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    api_base_url: AnyHttpUrl = "http://localhost:8000"
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
