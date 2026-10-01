"""HTTP read models, without copies of backend domain enums."""

from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel


class Heuristic(BaseModel):
    score: float
    rationale: str


class Idea(BaseModel):
    id: UUID
    title: str
    concept: str
    content_pillar: str
    format: str
    hook_idea: str
    rationale: str
    novelty_heuristic: Heuristic
    visual_potential_heuristic: Heuristic
    status: str


class Ideas(BaseModel):
    items: list[Idea]
    total: int
    limit: int
    offset: int


class Competitor(BaseModel):
    name: str
    platform: str
    url: AnyHttpUrl
    niche: str
    example_titles: list[str]
    observed_formats: list[str]
    typical_length_seconds: int | None
    publishing_frequency: str
    notes: str


class Competitors(BaseModel):
    items: list[Competitor]
    total: int
    limit: int
    offset: int
