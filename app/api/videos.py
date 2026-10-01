"""Response projections for video pages; backend owns statuses and workflow."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, RootModel


class Video(BaseModel):
    id: UUID
    title: str
    status: str
    language: str
    format: str
    duration_target: int
    budget_limit_usd: Decimal


class Videos(BaseModel):
    items: list[Video]
    total: int
    limit: int
    offset: int


class Task(BaseModel):
    id: UUID
    kind: str
    status: str
    attempts: int
    error_category: str | None = None


class Status(BaseModel):
    status: str
    updated_at: str
    has_active_tasks: bool
    tasks: list[Task]


class Scene(BaseModel):
    id: UUID
    position: int
    duration: Decimal
    narration: str
    visual_prompt: str
    visual_type: str
    mood: str
    caption_emphasis: list[str]


class Scenes(RootModel[list[Scene]]):
    pass


class Asset(BaseModel):
    id: UUID
    scene_id: UUID | None
    type: str
    content_type: str
    size_bytes: int


class Assets(RootModel[list[Asset]]):
    pass
