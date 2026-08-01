from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from threading import BoundedSemaphore
from time import monotonic
from typing import Any

from fastapi import FastAPI, HTTPException, Response

from services.model_runtime.adapters import AdapterUnavailable, ModelAdapter, create_adapter
from services.shared.contracts import CONTRACT_VERSION, ErrorCode, InferenceError, InferenceRequest, InferenceResponse, InferenceStatus

logger = logging.getLogger("model-service")


def _mode() -> str: return os.getenv("MODEL_MODE", "mock").lower()
def _configured_ready(service: str) -> bool: return os.getenv(f"{service.upper()}_READY", os.getenv("MODEL_READY", "true")).lower() in {"1", "true", "yes"}


def _mock_result(service: str, request: InferenceRequest) -> dict[str, Any]:
    if service == "florence": return {"detections": [{"label": value, "box": [0., 0., 1., 1.], "confidence": 1.} for value in request.payload.get("candidates", [])], "generated_at": datetime.now(UTC).isoformat()}
    if service == "grounding": return {"verified": True, "detections": request.payload.get("detections", []), "generated_at": datetime.now(UTC).isoformat()}
    if service == "sam": return {"segments": [{**value, "mask_area": 1.} for value in request.payload.get("detections", [])]}
    return {"embeddings": [], "dimensions": 0}


def create_model_app(service_name: str) -> FastAPI:
    app = FastAPI(title=f"Where Is It {service_name.title()} Service", version="0.2.0")
    adapter: ModelAdapter | None = None
    load_error: str | None = None
    slots = BoundedSemaphore(int(os.getenv("MODEL_MAX_CONCURRENCY", "1")))

    def runtime_details() -> dict[str, object]:
        details: dict[str, object] = {
            "device": os.getenv("MODEL_DEVICE", "cpu"),
            "dtype": os.getenv("MODEL_DTYPE", "float16"),
        }
        try:
            import torch

            details["torch_version"] = torch.__version__
            if str(details["device"]).startswith("cuda") and torch.cuda.is_available():
                index = torch.device(str(details["device"])).index or 0
                props = torch.cuda.get_device_properties(index)
                details.update(
                    cuda_available=True,
                    gpu_name=props.name,
                    compute_capability=f"{props.major}.{props.minor}",
                    gpu_memory_gb=round(props.total_memory / 1024 ** 3, 1),
                )
            else:
                details["cuda_available"] = False
        except (ImportError, RuntimeError, ValueError) as error:
            details["runtime_error"] = str(error)
        return details

    def version() -> str: return adapter.model_version if adapter else os.getenv(f"{service_name.upper()}_MODEL_VERSION", os.getenv("MODEL_VERSION", "mock-v1"))

    @app.on_event("startup")
    def load_model() -> None:
        nonlocal adapter, load_error
        if _mode() == "mock" or not _configured_ready(service_name): return
        try:
            if os.getenv("MODEL_CACHE_DIR"): os.environ.setdefault("HF_HOME", os.environ["MODEL_CACHE_DIR"])
            adapter = create_adapter(service_name); adapter.load()
        except (AdapterUnavailable, OSError, RuntimeError, ValueError) as error:
            adapter, load_error = None, str(error); logger.exception("model_load_failed service=%s", service_name)

    @app.get("/health/live")
    def live() -> dict[str, str]: return {"status": "ok", "service": service_name}

    @app.get("/health/ready")
    def ready(response: Response) -> dict[str, object]:
        available = _configured_ready(service_name) and (_mode() == "mock" or adapter is not None)
        if not available: response.status_code = 503
        return {"status": "ready" if available else "not_ready", "service": service_name, "mode": _mode(), "model_version": version(), **runtime_details(), "max_concurrency": int(os.getenv("MODEL_MAX_CONCURRENCY", "1")), "error": load_error}

    @app.post("/v1/infer", response_model=InferenceResponse)
    def infer(request: InferenceRequest, response: Response) -> InferenceResponse:
        started = monotonic()
        if request.contract_version != CONTRACT_VERSION: raise HTTPException(status_code=422, detail="unsupported internal contract version")
        available = _configured_ready(service_name) and (_mode() == "mock" or adapter is not None)
        if not available:
            response.status_code = 503; result = InferenceResponse(request_id=request.request_id, model_name=service_name, model_version=version(), status=InferenceStatus.FAILED, error=InferenceError(code=ErrorCode.MODEL_NOT_READY, message=load_error or "model is not ready", retryable=True))
        else:
            try:
                if not slots.acquire(timeout=request.deadline_ms / 1000): raise TimeoutError("model concurrency limit reached")
                try: payload = _mock_result(service_name, request) if _mode() == "mock" else adapter.infer(request)
                finally: slots.release()
                result = InferenceResponse(request_id=request.request_id, model_name=service_name, model_version=version(), status=InferenceStatus.OK, result=payload)
            except TimeoutError as error:
                response.status_code = 504; result = InferenceResponse(request_id=request.request_id, model_name=service_name, model_version=version(), status=InferenceStatus.FAILED, error=InferenceError(code=ErrorCode.DEADLINE_EXCEEDED, message=str(error), retryable=True))
            except (OSError, RuntimeError, ValueError) as error:
                logger.exception("model_inference_failed service=%s request_id=%s", service_name, request.request_id); response.status_code = 422 if isinstance(error, ValueError) else 500
                result = InferenceResponse(request_id=request.request_id, model_name=service_name, model_version=version(), status=InferenceStatus.FAILED, error=InferenceError(code=ErrorCode.INVALID_REQUEST if isinstance(error, ValueError) else ErrorCode.SERVICE_UNAVAILABLE, message=str(error), retryable=not isinstance(error, ValueError)))
        logger.info("model_inference service=%s request_id=%s model_version=%s status=%s latency_ms=%.1f", service_name, request.request_id, version(), result.status.value, (monotonic() - started) * 1000)
        return result
    return app
