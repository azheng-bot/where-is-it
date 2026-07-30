from __future__ import annotations

import os
import logging
from time import monotonic
from pathlib import Path
import sys

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

class TranscriptionResponse(BaseModel):
    text: str = ""
    provider: str
    model_version: str
    status: str
    language: str | None = None
    confidence: float | None = None
    error_code: str | None = None

logger = logging.getLogger("asr-service")
app = FastAPI(title="Where Is It ASR Service", version="0.1.0")


def is_ready() -> bool:
    return os.getenv("ASR_READY", "true").lower() in {"1", "true", "yes"}


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "asr"}


@app.get("/health/ready")
def ready(response: Response) -> dict[str, object]:
    available = is_ready()
    if not available:
        response.status_code = 503
    return {
        "status": "ready" if available else "not_ready",
        "service": "asr",
        "mode": os.getenv("ASR_MODE", "mock"),
        "model_version": os.getenv("ASR_MODEL_VERSION", "mock-v1"),
        "device": os.getenv("ASR_DEVICE", "cpu"),
    }


@app.post("/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe(request: Request, response: Response) -> TranscriptionResponse:
    content_type = request.headers.get("content-type", "")
    audio = await request.body()
    if content_type not in {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}:
        response.status_code = 415
        return TranscriptionResponse(provider="asr", model_version=os.getenv("ASR_MODEL_VERSION", "mock-v1"), status="failed", error_code="unsupported_media_type")
    if not audio:
        response.status_code = 422
        return TranscriptionResponse(provider="asr", model_version=os.getenv("ASR_MODEL_VERSION", "mock-v1"), status="failed", error_code="empty_audio")
    if not is_ready():
        response.status_code = 503
        return TranscriptionResponse(provider="asr", model_version=os.getenv("ASR_MODEL_VERSION", "mock-v1"), status="failed", error_code="model_not_ready")
    return TranscriptionResponse(
        text=os.getenv("ASR_MOCK_TEXT", "我的钥匙在哪里？"),
        provider="mock-asr",
        model_version=os.getenv("ASR_MODEL_VERSION", "mock-v1"),
        status="success",
        language="zh",
        confidence=1.0,
    )