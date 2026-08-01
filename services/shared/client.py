from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contracts import ErrorCode, InferenceError, InferenceRequest, InferenceResponse, InferenceStatus

@dataclass
class ServiceCallError(Exception):
    code: ErrorCode
    message: str
    retryable: bool = True

class InternalServiceClient:
    """Small synchronous client that carries correlation and deadline metadata."""

    def __init__(self, base_url: str, name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.name = name

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        if not self.base_url:
            raise ServiceCallError(ErrorCode.SERVICE_UNAVAILABLE, f"{self.name} is not configured", False)
        timeout = max(0.05, request.deadline_ms / 1000)
        http_request = Request(
            f"{self.base_url}/v1/infer",
            data=request.model_dump_json().encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Request-ID": request.request_id},
            method="POST",
        )
        started = monotonic()
        try:
            with urlopen(http_request, timeout=timeout) as response:
                return InferenceResponse.model_validate_json(response.read())
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            if error.code == 422:
                code = ErrorCode.CONTRACT_MISMATCH
            elif error.code in {408, 504}:
                code = ErrorCode.DEADLINE_EXCEEDED
            else:
                code = ErrorCode.SERVICE_UNAVAILABLE
            raise ServiceCallError(code, body or f"{self.name} returned HTTP {error.code}", code != ErrorCode.CONTRACT_MISMATCH) from error
        except (URLError, TimeoutError, OSError) as error:
            code = ErrorCode.DEADLINE_EXCEEDED if isinstance(error, TimeoutError) else ErrorCode.SERVICE_UNAVAILABLE
            raise ServiceCallError(code, f"{self.name}: {error}") from error

    def degraded_response(self, request: InferenceRequest, error: ServiceCallError) -> InferenceResponse:
        return InferenceResponse(
            request_id=request.request_id,
            model_name=self.name,
            model_version="unavailable",
            status=InferenceStatus.DEGRADED,
            error=InferenceError(code=error.code, message=error.message, retryable=error.retryable),
        )