from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import QueryRequest, QueryResult, RenameRequest, TranscriptionResult
from .repository import Repository

repository = Repository(settings.database_path)
app = FastAPI(title="Where Is It API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup() -> None:
    settings.evidence_dir.mkdir(parents=True, exist_ok=True)
    repository.migrate()
    repository.seed_demo_data()


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "database": "connected", "vision": "demo"}


@app.get("/api/room/state")
def room_state() -> dict[str, object]:
    objects = repository.list_objects()
    return {"camera": {"status": "online", "label": "卧室摄像头", "updated_at": "刚刚"}, "catalog": {"objects": len(objects), "locations": len(repository.list_locations())}, "vision": {"status": "ready", "profile": "cpu-demo"}}


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
    return repository.query(body.text)


@app.post("/api/speech/transcribe", response_model=TranscriptionResult)
async def transcribe(audio: UploadFile = File(...)) -> TranscriptionResult:
    if audio.content_type not in {"audio/webm", "audio/wav", "audio/mpeg", "audio/mp4"}:
        raise HTTPException(status_code=415, detail="请上传浏览器录制的音频文件")
    if audio.size and audio.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="录音不能超过十分钟")
    return TranscriptionResult(text="我的钥匙在哪里", provider="demo-fallback", fallback=True)
