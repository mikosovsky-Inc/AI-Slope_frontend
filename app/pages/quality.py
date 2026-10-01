"""Read-only projections of backend quality reports; no local quality decisions."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, RootModel

from app.api.client import BackendError
from app.api.panel import User, read
from app.api.videos import Video
from app.pages.channels import SESSION, login
from app.pages.operations import failure, page

router = APIRouter()


class Check(BaseModel):
    code: str
    outcome: str
    scene_id: UUID | None = None
    asset_id: UUID | None = None
    repair: str | None = None


class Report(BaseModel):
    checks: list[Check] = []
    duration_seconds: float | None = None
    target_seconds: float | None = None
    visual_provider: str | None = None


class QualityCheck(BaseModel):
    id: UUID
    task_id: UUID
    render_task_id: UUID
    final_asset_id: UUID | None
    attempt: int
    status: str
    report_json: Report
    created_at: datetime
    completed_at: datetime | None


class QualityChecks(RootModel[list[QualityCheck]]):
    pass


@router.get("/videos/{video_id}/quality")
async def quality(request: Request, video_id: UUID):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    try:
        backend = request.app.state.backend
        user = await read(backend, "/auth/me", token, User)
        video = await read(backend, f"/videos/{video_id}", token, Video)
        reports = await read(backend, f"/videos/{video_id}/quality-checks", token, QualityChecks)
        return page(request, view="quality", user=user, video=video, reports=reports.root)
    except BackendError as exc:
        return failure(request, exc, view="quality")
