from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .asr import AsrClient, AsrServiceError
from .llm import AnswerComposer
from .models import ObservationBatch, QueryRequest, QueryResult, RenameRequest, TranscriptionResult
from .repository import Repository

repository = Repository(settings.database_path)
composer = AnswerComposer(settings)
app = FastAPI(title="Where Is It API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    repository.migrate()


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "database": "connected", "vision": "fixture"}


@app.get("/api/room/state")
def room_state() -> dict[str, object]:
    objects = repository.list_objects()
    return {"camera": {"status": "online", "label": "Mock 客厅摄像头", "updated_at": "持续循环", "frame_url": f"{settings.vision_public_url}/api/camera/frame", "stream_url": f"{settings.vision_public_url}/api/camera/stream", "source_kind": "mock-video"}, "catalog": {"objects": len(objects), "locations": len(repository.list_locations())}, "vision": {"status": "ready", "profile": "mock-video-stream"}}


@app.post("/internal/observations/batch")
def ingest_observations(batch: ObservationBatch) -> dict[str, int | str]:
    created = repository.ingest_observations(batch.observations, batch.observed_at, batch.fixture_image_path, settings.evidence_dir)
    return {"source": batch.source, "accepted": len(batch.observations), "created": created}


@app.get("/api/objects")
def list_objects():
    return repository.list_objects()


@app.patch("/api/objects/{object_id}")
def patch_object(object_id: str, body: RenameRequest):
    try:
        result = repository.rename_object(object_id, body.name, body.aliases)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="未找到该物品")
    return result


@app.get("/api/locations")
def list_locations():
    return repository.list_locations()


@app.patch("/api/locations/{location_id}")
def patch_location(location_id: str, body: RenameRequest):
    try:
        result = repository.rename_location(location_id, body.name)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="未找到该位置")
    return result


@app.post("/api/query", response_model=QueryResult)
def query(body: QueryRequest) -> QueryResult:
    result = repository.query(body.text, "http://127.0.0.1:8000")
    answer, llm_ms = composer.compose(result)
    result.answer = answer
    result.timings["llm_ms"] = llm_ms
    result.timings["total_ms"] = result.timings.get("resolve_ms", 0) + result.timings.get("lookup_ms", 0) + llm_ms
    return result


@app.get("/api/evidence/{evidence_id}")
def evidence(evidence_id: str):
    path = repository.evidence_path(evidence_id)
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="证据图片已不存在")
    return FileResponse(path)


@app.post("/api/speech/transcribe", response_model=TranscriptionResult)
async def transcribe(audio: UploadFile = File(...)) -> TranscriptionResult:
    supported_types = {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}
    if audio.content_type not in supported_types:
        return TranscriptionResult(provider="api", status="failed", error_code="unsupported_media_type")
    payload = await audio.read()
    if not payload:
        return TranscriptionResult(provider="api", status="failed", error_code="empty_audio")
    if len(payload) > 10 * 1024 * 1024:
        return TranscriptionResult(provider="api", status="failed", error_code="audio_too_large")
    try:
        result = AsrClient(settings.asr_service_url, settings.asr_timeout_seconds).transcribe(payload, audio.content_type)
    except AsrServiceError as error:
        return TranscriptionResult(provider="asr", status="failed", error_code=error.code)
    return TranscriptionResult(
        text=result.text,
        provider=result.provider,
        model_version=result.model_version,
        language=result.language,
        confidence=result.confidence,
        status="success",
    )