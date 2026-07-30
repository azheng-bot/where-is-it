from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.shared.contracts import ErrorCode

@dataclass
class AsrServiceError(Exception):
    code: str
    message: str

@dataclass
class AsrServiceResult:
    text: str
    provider: str
    model_version: str
    language: str | None = None
    confidence: float | None = None

class AsrClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def transcribe(self, audio: bytes, content_type: str) -> AsrServiceResult:
        if not self.base_url:
            raise AsrServiceError("asr_not_configured", "ASR service is not configured")
        request = Request(
            f"{self.base_url}/v1/transcribe",
            data=audio,
            headers={"Content-Type": content_type, "X-Request-ID": uuid.uuid4().hex},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read())
        except HTTPError as error:
            try:
                payload = json.loads(error.read())
                code = payload.get("error_code", "asr_service_error")
            except (ValueError, UnicodeDecodeError):
                code = "asr_service_error"
            if error.code in {408, 504}:
                code = ErrorCode.DEADLINE_EXCEEDED.value
            raise AsrServiceError(code, f"ASR service returned HTTP {error.code}") from error
        except (URLError, TimeoutError, OSError) as error:
            code = ErrorCode.DEADLINE_EXCEEDED.value if isinstance(error, TimeoutError) else ErrorCode.SERVICE_UNAVAILABLE.value
            raise AsrServiceError(code, f"ASR service is unavailable: {error}") from error
        if payload.get("status") != "success" or not payload.get("text"):
            raise AsrServiceError(payload.get("error_code", "asr_transcription_failed"), "ASR service did not return transcription text")
        return AsrServiceResult(
            text=payload["text"], provider=payload.get("provider", "asr"), model_version=payload.get("model_version", "unknown"),
            language=payload.get("language"), confidence=payload.get("confidence"),
        )