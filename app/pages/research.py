"""Source provenance from the backend; no searching or fact checking in the UI."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError

from app.api.client import BackendError
from app.api.panel import User, read
from app.api.videos import Video
from app.pages.channels import SESSION, login
from app.pages.operations import failure, page

router = APIRouter()


class Source(BaseModel):
    source_url: str
    source_title: str

    @property
    def link(self) -> str | None:
        try:
            url = AnyHttpUrl(self.source_url)
        except ValidationError:
            return None
        return str(url) if not url.username and not url.password else None


class Document(Source):
    id: UUID
    content: str
    retrieved_at: datetime


class Fact(Source):
    id: UUID
    document_id: UUID
    statement: str
    confidence: float = Field(ge=0, le=1)


class Research(BaseModel):
    video_id: UUID
    documents: list[Document]
    facts: list[Fact]


class Citation(BaseModel):
    position: int
    fact: Fact


class Script(BaseModel):
    video_id: UUID
    citations: list[Citation]


@router.get("/videos/{video_id}/sources")
async def sources(request: Request, video_id: UUID):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    try:
        backend = request.app.state.backend
        user = await read(backend, "/auth/me", token, User)
        video = await read(backend, f"/videos/{video_id}", token, Video)
        data, script = None, None
        if video.format == "top5":
            data = await read(backend, f"/videos/{video_id}/research", token, Research)
            if data.video_id != video_id:
                raise BackendError(502)
            try:
                script = await read(backend, f"/videos/{video_id}/script", token, Script)
            except BackendError as exc:
                if exc.status != 404:
                    raise
            if script and script.video_id != video_id:
                raise BackendError(502)
        return page(request, view="sources", user=user, video=video, research=data, script=script)
    except BackendError as exc:
        return failure(request, exc, view="sources")
