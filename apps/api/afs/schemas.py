import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool


class FounderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str
    collection_name: str
    biography: str
    status: str


class TopicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    slug: str
    name: str
    description: str
    parent_id: uuid.UUID | None


class CandidateCreate(BaseModel):
    founder_id: uuid.UUID
    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    publisher: str | None = Field(default=None, max_length=240)
    content_type: str = Field(default="web_page", max_length=80)
    discovery_query: str | None = Field(default=None, max_length=500)


class CandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    founder_id: uuid.UUID
    original_url: str
    normalized_url: str
    title: str
    publisher: str | None
    content_type: str
    status: str
    score: float
    score_breakdown: dict[str, float]
    robots_status: str
    review_note: str | None
    created_at: datetime


class CandidateReview(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(min_length=3, max_length=2000)
    source_tier: Literal["A", "B", "C", "D"] = "B"


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    founder_id: uuid.UUID
    canonical_url: str
    title: str
    publisher: str | None
    author: str | None
    publication_date: date | None
    content_type: str
    source_tier: str
    approval_status: str
    speaker_verified: bool
    quality_score: float
    underlying_work_id: uuid.UUID


class CorrectionCreate(BaseModel):
    source_id: uuid.UUID | None = None
    category: Literal[
        "wrong_attribution",
        "incorrect_date",
        "broken_source",
        "misleading_interpretation",
        "duplicate",
        "copyright_concern",
        "removal_request",
    ]
    description: str = Field(min_length=20, max_length=5000)
    reporter_email: EmailStr | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    founder_id: uuid.UUID | None = None
    topic: str | None = Field(default=None, max_length=160)
    date_from: date | None = None
    date_to: date | None = None
    debug: bool = False


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    title: str
    publisher: str | None
    publication_date: date | None
    url: str
    text: str
    start_seconds: float | None
    end_seconds: float | None
    combined_rank: float


class JobCreate(BaseModel):
    job_type: str = Field(min_length=3, max_length=100)
    payload: dict[str, object] = Field(default_factory=dict)


class ManualImportRequest(BaseModel):
    founder_id: uuid.UUID
    original_source_url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=240)
    publication_date: date | None = None
    content_type: Literal["plain_text", "markdown", "transcript", "srt", "vtt", "json"]
    attribution: str = Field(min_length=2, max_length=500)
    rights_note: str = Field(min_length=3, max_length=1000)
    content: str = Field(min_length=20, max_length=5_000_000)


class FileImportMetadata(BaseModel):
    founder_id: uuid.UUID
    original_source_url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    publisher: str = Field(min_length=1, max_length=240)
    publication_date: date | None = None
    attribution: str = Field(min_length=2, max_length=500)
    rights_note: str = Field(min_length=3, max_length=1000)
