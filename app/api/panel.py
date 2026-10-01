"""Read-only HTTP response projections; domain enums remain backend-owned."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.api.client import BackendError


class User(BaseModel):
    email: str
    role: str


class Costs(BaseModel):
    currency: str
    effective_usd: Decimal
    actual_usd: Decimal
    estimated_usd: Decimal
    pending_actual_events: int


class RecentVideo(BaseModel):
    id: UUID
    title: str
    status: str
    language: str


class Dashboard(BaseModel):
    channels: int
    active_channels: int
    videos: int
    videos_by_status: dict[str, int]
    costs: Costs
    recent_videos: list[RecentVideo]


class Channel(BaseModel):
    id: UUID
    name: str
    idea: str
    status: str
    language: str
    videos_per_day: int
    budget_per_video_usd: Decimal
    autopilot_mode: str


class ChannelPage(BaseModel):
    items: list[Channel]
    total: int
    limit: int
    offset: int


async def read(backend, path, token, model, **kwargs):
    payload = await backend.request("GET", path, token=token, **kwargs)
    try:
        return model.model_validate(payload)
    except ValidationError:
        raise BackendError(502) from None
