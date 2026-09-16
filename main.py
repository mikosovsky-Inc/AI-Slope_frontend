from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AnyHttpUrl, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    api_base_url: AnyHttpUrl = "http://localhost:8000"


class PublicConfig(BaseModel):
    api_base_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


app = FastAPI(title="AI-Slop Frontend", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")


@app.get("/config", response_model=PublicConfig)
def config() -> JSONResponse:
    public = PublicConfig(api_base_url=str(get_settings().api_base_url).rstrip("/"))
    return JSONResponse(public.model_dump(), headers={"Cache-Control": "no-store"})


@app.get("/")
@app.get("/login")
@app.get("/register")
@app.get("/app")
def index() -> FileResponse:
    return FileResponse(ROOT / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
def apple_touch_icon() -> FileResponse:
    return FileResponse(ROOT / "assets" / "icons" / "apple-touch-icon.png", media_type="image/png")
