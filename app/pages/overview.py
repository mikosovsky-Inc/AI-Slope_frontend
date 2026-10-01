"""Channel overview through the existing owner-scoped backend API."""

from datetime import date
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.client import BackendError
from app.api.panel import Channel, Costs, User, read
from app.pages.channels import SESSION, login
from app.pages.operations import failure, page

router = APIRouter()


class Plan(BaseModel):
    day: date
    status: str
    target: int
    reason: str | None


class Overview(BaseModel):
    channel: Channel
    videos_by_status: dict[str, int]
    ideas_by_status: dict[str, int]
    costs: Costs
    latest_plan: Plan | None


@router.get("/channels/{channel_id}/overview")
async def overview(request: Request, channel_id: UUID):
    token = request.cookies.get(SESSION)
    if not token:
        return login()
    try:
        backend = request.app.state.backend
        user = await read(backend, "/auth/me", token, User)
        data = await read(backend, f"/channels/{channel_id}/overview", token, Overview)
        links = {
            kind: [
                {
                    "status": status,
                    "count": count,
                    "url": f"/channels/{channel_id}/{kind}?" + urlencode({"status": status}),
                }
                for status, count in counts.items()
            ]
            for kind, counts in (("videos", data.videos_by_status), ("ideas", data.ideas_by_status))
        }
        return page(
            request, view="overview", user=user, channel=data.channel, data=data, links=links
        )
    except BackendError as exc:
        return failure(request, exc, view="overview")
