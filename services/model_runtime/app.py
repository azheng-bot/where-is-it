from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Response

from services.shared.contracts import (
    CONTRACT_VERSION,
    ErrorCode,
    InferenceError,
    InferenceRequest,
    InferenceResponse,
    InferenceStatus,
)


def _ready(service_name: str) -> bool:
    return os.getenv(f"{service_name.upper()}_READY", os.getenv("MODEL_READY", "true")).lower() in {"1", "true", "yes"}


def _result_for(service_name: str, request: InferenceRequest) -> dict[str, Any]:
    if service_name == "florence":
        return {"candidates": request.payload.get("candidates", []), "generated_at": datetime.now(UTC).isoformat()}
    if service_name == "grounding":
        return {"verified": True, "boxes": request.payload.get("boxes", []), "generated_at": datetime.now(UTC).isoformat()}
    if service_name == "sam":
        return {"masks": request.payload.get("masks", []), "boxes": request.payload.get("boxes", [])}
    if service_name == "embedding":
        return {"embedding": request.payload.get("embedding", [0.0, 0.0, 0.0]), "dimensions": 3}
    return {"accepted": True}


logger = logging.getLogger("model-service")

def create_model_app(service_name: str) -> FastAPI:
    model_version = os.getenv(f"{service_name.upper()}_MODEL_VERSION", os.getenv("MODEL_VERSION", "mock-v1"))
    app = FastAPI(title=f"Where Is It {service_name.title()} Service", version="0.1.0")

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/health/ready")
    def ready(response: Response) -> dict[str, object]:
        available = _ready(service_name)
        if not available:
            response.status_code = 503
        return {
            "status": "ready" if available else "not_ready",
            "service": service_name,
            "mode": os.getenv("MODEL_MODE", "mock"),
            "model_version": model_version,
            "device": os.getenv("MODEL_DEVICE", "cpu"),
            "max_concurrency": int(os.getenv("MODEL_MAX_CONCURRENCY", "1")),
        }

    @app.post("/v1/infer", response_model=InferenceResponse)
    def infer(request: InferenceRequest, response: Response) -> InferenceResponse:
        started = monotonic()
        if request.contract_version != CONTRACT_VERSION:
            raise HTTPException(status_code=422, detail="unsupported internal contract version")
        if not _ready(service_name):
            response.status_code = 503
            result = InferenceResponse(
                request_id=request.request_id,
                model_name=service_name,
                model_version=model_version,
                status=InferenceStatus.FAILED,
                error=InferenceError(code=ErrorCode.MODEL_NOT_READY, message="model is not ready", retryable=True),
            )
        else:
            result = InferenceResponse(
                request_id=request.request_id,
                model_name=service_name,
                model_version=model_version,
                status=InferenceStatus.OK,
                result=_result_for(service_name, request),
            )
        logger.info("model_inference service=%s request_id=%s model_version=%s status=%s latency_ms=%.1f", service_name, request.request_id, model_version, result.status.value, (monotonic() - started) * 1000)
        return result

    return app