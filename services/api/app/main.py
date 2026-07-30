from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
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
    return {"camera": {"status": "online", "label": "Mock 卧室摄像头", "updated_at": "持续循环", "frame_url": f"{settings.vision_public_url}/api/camera/frame"}, "catalog": {"objects": len(objects), "locations": len(repository.list_locations())}, "vision": {"status": "ready", "profile": "fixture-mock"}}


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
    if audio.content_type not in {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}:
        raise HTTPException(status_code=415, detail="请上传浏览器录制的音频文件")
    if audio.size and audio.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="录音不能超过十分钟")
    return TranscriptionResult(text="我的钥匙在哪里", provider="demo-fallback", fallback=True)
