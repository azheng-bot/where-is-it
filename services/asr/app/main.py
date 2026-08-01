from __future__ import annotations

import importlib.util
import logging
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Callable, Protocol

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

SUPPORTED_MEDIA_TYPES = frozenset({"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"})
DEFAULT_MAX_AUDIO_BYTES = 10 * 1024 * 1024


class TranscriptionResponse(BaseModel):
    text: str = ""
    provider: str
    model_version: str
    status: str
    language: str | None = None
    confidence: float | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class AsrSettings:
    mode: str = "mock"
    model: str = "small"
    model_version: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    model_cache_dir: str | None = None
    max_audio_bytes: int = DEFAULT_MAX_AUDIO_BYTES
    ready_override: bool = True

    @classmethod
    def from_environment(cls) -> "AsrSettings":
        device = os.getenv("ASR_DEVICE", "cpu").lower()
        compute_type = os.getenv("ASR_COMPUTE_TYPE", "float16" if device == "cuda" else "int8")
        return cls(mode=os.getenv("ASR_MODE", "mock").lower(), model=os.getenv("ASR_MODEL", "small"), model_version=os.getenv("ASR_MODEL_VERSION", os.getenv("ASR_MODEL", "small")), device=device, compute_type=compute_type, model_cache_dir=os.getenv("ASR_MODEL_CACHE_DIR") or None, max_audio_bytes=int(os.getenv("ASR_MAX_AUDIO_BYTES", str(DEFAULT_MAX_AUDIO_BYTES))), ready_override=os.getenv("ASR_READY", "true").lower() in {"1", "true", "yes"})


@dataclass(frozen=True)
class Transcription:
    text: str
    provider: str
    model_version: str
    language: str = "zh"
    confidence: float | None = None


@dataclass
class TranscriptionError(Exception):
    code: str
    message: str
    status_code: int = 500


class TranscriptionAdapter(Protocol):
    def transcribe(self, audio: bytes, media_type: str) -> Transcription: ...


class MockAdapter:
    """Development-only adapter that keeps the local product loop usable without a model."""

    def __init__(self, settings: AsrSettings) -> None:
        self.settings = settings

    def transcribe(self, audio: bytes, media_type: str) -> Transcription:
        return Transcription(text=os.getenv("ASR_MOCK_TEXT", "我的钥匙在哪里？"), provider="mock-asr", model_version=self.settings.model_version, confidence=1.0)


class FasterWhisperAdapter:
    """Lazy faster-whisper adapter so ASR model startup never blocks other services."""

    def __init__(self, settings: AsrSettings, model_factory: Callable[..., object] | None = None) -> None:
        self.settings = settings
        self._model_factory = model_factory
        self._model: object | None = None
        self._model_lock = Lock()

    def is_available(self) -> bool:
        return self._model_factory is not None or importlib.util.find_spec("faster_whisper") is not None

    def _get_model(self) -> object:
        with self._model_lock:
            if self._model is not None:
                return self._model
            factory = self._model_factory
            if factory is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as error:
                    raise TranscriptionError("model_unavailable", "faster-whisper is not installed", 503) from error
                factory = WhisperModel
            try:
                kwargs: dict[str, object] = {"device": self.settings.device, "compute_type": self.settings.compute_type}
                if self.settings.model_cache_dir:
                    kwargs["download_root"] = self.settings.model_cache_dir
                self._model = factory(self.settings.model, **kwargs)
            except Exception as error:
                raise TranscriptionError("model_load_failed", "Unable to load ASR model", 503) from error
            return self._model

    def transcribe(self, audio: bytes, media_type: str) -> Transcription:
        suffix = {"audio/webm": ".webm", "audio/wav": ".wav", "audio/mpeg": ".mp3", "audio/mp4": ".mp4"}[media_type]
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary_file:
                temporary_file.write(audio)
                temporary_path = Path(temporary_file.name)
            model = self._get_model()
            segments, info = model.transcribe(str(temporary_path), language="zh", task="transcribe", beam_size=5, vad_filter=True, condition_on_previous_text=False)
            segment_list = list(segments)
        except TranscriptionError:
            raise
        except Exception as error:
            raise TranscriptionError("transcription_failed", "ASR could not transcribe the audio", 422) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        text = "".join(str(getattr(segment, "text", "")) for segment in segment_list).strip()
        if not text:
            raise TranscriptionError("empty_transcription", "ASR returned no speech", 422)
        log_probs = [float(value) for segment in segment_list if (value := getattr(segment, "avg_logprob", None)) is not None]
        confidence = min(1.0, max(0.0, math.exp(sum(log_probs) / len(log_probs)))) if log_probs else None
        return Transcription(text=text, provider="faster-whisper", model_version=self.settings.model_version, language=getattr(info, "language", None) or "zh", confidence=confidence)


class TranscriptionService:
    def __init__(self, settings: AsrSettings, adapter: TranscriptionAdapter | None = None) -> None:
        self.settings = settings
        if adapter is not None:
            self.adapter = adapter
        elif settings.mode == "mock":
            self.adapter = MockAdapter(settings)
        elif settings.mode == "faster-whisper":
            self.adapter = FasterWhisperAdapter(settings)
        else:
            self.adapter = None

    def readiness(self) -> tuple[bool, str | None]:
        if not self.settings.ready_override:
            return False, "model_not_ready"
        if self.adapter is None:
            return False, "invalid_asr_mode"
        if isinstance(self.adapter, FasterWhisperAdapter) and not self.adapter.is_available():
            return False, "model_unavailable"
        return True, None

    def transcribe(self, audio: bytes, content_type: str) -> Transcription:
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise TranscriptionError("unsupported_media_type", "Unsupported audio type", 415)
        if not audio:
            raise TranscriptionError("empty_audio", "Audio body is empty", 422)
        if len(audio) > self.settings.max_audio_bytes:
            raise TranscriptionError("audio_too_large", "Audio exceeds the configured size limit", 413)
        available, error_code = self.readiness()
        if not available:
            raise TranscriptionError(error_code or "model_not_ready", "ASR service is not ready", 503)
        assert self.adapter is not None
        return self.adapter.transcribe(audio, media_type)


logger = logging.getLogger("asr-service")
settings = AsrSettings.from_environment()
service = TranscriptionService(settings)
app = FastAPI(title="Where Is It ASR Service", version="0.2.0")


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok", "service": "asr"}


@app.get("/health/ready")
def ready(response: Response) -> dict[str, object]:
    available, error_code = service.readiness()
    if not available:
        response.status_code = 503
    return {"status": "ready" if available else "not_ready", "service": "asr", "mode": service.settings.mode, "model_version": service.settings.model_version, "device": service.settings.device, "error_code": error_code}


@app.post("/v1/transcribe", response_model=TranscriptionResponse)
async def transcribe(request: Request, response: Response) -> TranscriptionResponse:
    try:
        result = service.transcribe(await request.body(), request.headers.get("content-type", ""))
    except TranscriptionError as error:
        response.status_code = error.status_code
        return TranscriptionResponse(provider="asr", model_version=service.settings.model_version, status="failed", error_code=error.code)
    return TranscriptionResponse(text=result.text, provider=result.provider, model_version=result.model_version, status="success", language=result.language, confidence=result.confidence)
