"""Display the backend's visual plan without making production decisions."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.client import BackendError
from app.api.panel import User, read
from app.api.videos import Video
from app.pages.channels import SESSION, login
from app.pages.operations import failure, page

router = APIRouter()


class Prices(BaseModel):
    image_usd: Decimal
    video_second_usd: Decimal


class DirectedScene(BaseModel):
    id: UUID
    position: int
    duration: Decimal
    visual_prompt: str
    visual_type: str
    camera_motion: str
    visual_style: str
    importance: float
    generation_priority: int


class Direction(BaseModel):
    id: UUID
    video_id: UUID
    visual_budget_usd: Decimal
    estimated_cost_usd: Decimal
    requested_video_ratio: float
    pricing_snapshot: Prices
    created_at: datetime
    scenes: list[DirectedScene]


@router.get("/videos/{video_id}/direction")
async def direction(request: Request, video_id: UUID):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    try:
        backend = request.app.state.backend
        user = await read(backend, "/auth/me", token, User)
        video = await read(backend, f"/videos/{video_id}", token, Video)
        plan = None
        try:
            plan = await read(backend, f"/videos/{video_id}/direction", token, Direction)
        except BackendError as exc:
            if exc.status != 404:
                raise
        if plan and plan.video_id != video_id:
            raise BackendError(502)
        return page(request, view="direction", user=user, video=video, plan=plan)
    except BackendError as exc:
        return failure(request, exc, view="direction")
