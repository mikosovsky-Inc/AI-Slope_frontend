from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, RootModel

from app.api.panel import Costs
from app.api.videos import Scene, Task


class Cost(BaseModel):
    video_id: UUID
    provider: str
    operation: str
    model: str
    estimated_cost_usd: Decimal
    actual_cost_usd: Decimal | None
    created_at: str


class CostPage(BaseModel):
    summary: Costs
    items: list[Cost]
    total: int
    limit: int
    offset: int


class Budget(BaseModel):
    currency: str
    limit_usd: Decimal
    committed_usd: Decimal
    remaining_usd: Decimal


class Job(Task):
    owner_id: UUID
    video_id: UUID | None
    queue: str
    max_attempts: int
    request_id: str | None


class Jobs(BaseModel):
    items: list[Job]
    total: int
    limit: int
    offset: int
    counts: dict[str, int]


class TaskDetail(Task):
    video_id: UUID | None
    request_id: str | None = None


class Recovery(BaseModel):
    number: int
    action: str
    note: str
    created_at: str


class Recoveries(RootModel[list[Recovery]]):
    pass


class RevisionScene(Scene):
    camera_motion: str


class Revision(BaseModel):
    id: UUID
    number: int
    status: str
    final_asset_id: UUID | None
    scenes: list[RevisionScene]
    created_at: str


class Revisions(RootModel[list[Revision]]):
    pass
