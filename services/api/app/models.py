from datetime import datetime
from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, Field


class ObjectState(StrEnum):
    CURRENTLY_DETECTED = "currently_detected"
    NOT_CURRENTLY_DETECTED = "not_currently_detected"
    IDENTITY_UNCERTAIN = "identity_uncertain"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Room(BaseModel):
    room_id: str
    name: str


class Alias(BaseModel):
    alias: str


class LocationSummary(BaseModel):
    location_id: str
    name: str
    relation: str | None = None


class Location(BaseModel):
    location_id: str
    name: str
    normalized_name: str
    polygon: list[tuple[float, float]] = Field(default_factory=list)
    item_count: int = 0


class CatalogObject(BaseModel):
    object_id: str
    name: str
    system_name: str
    category: str
    aliases: list[str] = Field(default_factory=list)
    state: ObjectState
    current_location: LocationSummary | None = None
    last_location: LocationSummary | None = None
    observed_at: datetime | None = None
    confidence: float


class Observation(BaseModel):
    observation_id: str
    object_id: str
    location_id: str | None = None
    observed_at: datetime
    bounding_box: tuple[float, float, float, float]
    confidence: float


class Evidence(BaseModel):
    evidence_id: str
    image_url: str
    observed_at: datetime
    bounding_box: tuple[float, float, float, float]


class Prediction(BaseModel):
    location: LocationSummary
    confidence: ConfidenceLevel
    score: float
    basis: str
    is_inference: Literal[True] = True


class QueryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200)


class QueryResult(BaseModel):
    answer: str
    status: ObjectState | Literal["clarification", "not_found"]
    object: CatalogObject | None = None
    predictions: list[Prediction] = Field(default_factory=list, max_length=3)
    evidence: Evidence | None = None
    clarification_options: list[CatalogObject] = Field(default_factory=list)
    timings: dict[str, float]


class RenameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    aliases: list[str] | None = Field(default=None, max_length=12)


class TranscriptionResult(BaseModel):
    text: str
    provider: str
    fallback: bool
