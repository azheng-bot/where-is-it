from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

CONTRACT_VERSION = "v1"

class InferenceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"

class ErrorCode(StrEnum):
    SERVICE_UNAVAILABLE = "service_unavailable"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    CONTRACT_MISMATCH = "contract_mismatch"
    INVALID_REQUEST = "invalid_request"
    MODEL_NOT_READY = "model_not_ready"

class MediaReference(BaseModel):
    uri: str = Field(min_length=1, max_length=2048)
    media_type: str = Field(default="image/png", min_length=3, max_length=120)

class InferenceRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=120)
    contract_version: str = CONTRACT_VERSION
    deadline_ms: int = Field(gt=0, le=30_000)
    source: str = Field(min_length=1, max_length=80)
    frame_ref: MediaReference | None = None
    media_ref: MediaReference | None = None
    query: str | None = Field(default=None, max_length=500)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def requires_media_reference(self) -> "InferenceRequest":
        if self.frame_ref is None and self.media_ref is None:
            raise ValueError("frame_ref or media_ref is required")
        return self

class InferenceError(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool = False

class InferenceResponse(BaseModel):
    request_id: str
    contract_version: str = CONTRACT_VERSION
    model_name: str
    model_version: str
    status: InferenceStatus
    result: dict[str, Any] = Field(default_factory=dict)
    error: InferenceError | None = None

class ServiceDescriptor(BaseModel):
    name: str
    base_url: str = ""
    model_version: str = "mock-v1"
    mode: str = "mock"
    device: str = "cpu"
    max_concurrency: int = Field(default=1, ge=1, le=32)