from __future__ import annotations

import base64
import hmac
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest, Response, status

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from services.shared.client import InternalServiceClient, ServiceCallError
from services.shared.contracts import CONTRACT_VERSION, InferenceRequest, InferenceStatus, MediaReference

logger = logging.getLogger("vision-orchestrator")
MOCK_VIDEO_PATH = Path(os.getenv("CAMERA_MOCK_VIDEO_PATH", Path(__file__).parents[1] / "fixtures" / "media" / "indoor-living-room.mp4")).resolve()
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "mock-video").lower()
CAMERA_VIDEO_PATH = os.getenv("CAMERA_VIDEO_PATH", str(MOCK_VIDEO_PATH))
CAMERA_USB_INDEX = int(os.getenv("CAMERA_USB_INDEX", "0"))
CAMERA_RTSP_URL = os.getenv("CAMERA_RTSP_URL", "")
API_URL = os.getenv("API_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
INTERVAL_SECONDS = float(os.getenv("DISCOVERY_INTERVAL_SECONDS", "0.7"))
VISION_ROLE = os.getenv("VISION_ROLE", "receiver").lower()
VISION_INGEST_URL = os.getenv("VISION_INGEST_URL", "").rstrip("/")
VISION_PUSH_TOKEN = os.getenv("VISION_PUSH_TOKEN", "")
VISION_PUSH_TIMEOUT_SECONDS = float(os.getenv("VISION_PUSH_TIMEOUT_SECONDS", "5"))
VISION_PUSH_MAX_FRAME_BYTES = int(os.getenv("VISION_PUSH_MAX_FRAME_BYTES", str(10 * 1024 * 1024)))
PROMPTS = [value.strip() for value in os.getenv("VISION_PROMPTS", "keys,glasses,mug,bottle,laptop,backpack,notebook,headphones,remote control,table lamp").split(",") if value.strip()]
STAGE_URLS = {"florence": os.getenv("FLORENCE_SERVICE_URL", "http://127.0.0.1:8002"), "grounding": os.getenv("GROUNDING_SERVICE_URL", "http://127.0.0.1:8003"), "sam": os.getenv("SAM_SERVICE_URL", "http://127.0.0.1:8004"), "embedding": os.getenv("EMBEDDING_SERVICE_URL", "http://127.0.0.1:8005")}

if VISION_ROLE not in {"pusher", "receiver"}:
    raise ValueError("VISION_ROLE must be pusher or receiver")

class VideoFrameSource:
    """Latest-frame capture for files, USB devices, and RTSP streams."""
    def __init__(self) -> None:
        self.capture = None; self.lock = Lock(); self.frame_count = 0; self.latest_timestamp = "waiting for first frame"; self.connected = False; self.error: str | None = None; self.latest_jpeg: bytes | None = None

    def _target(self):
        if CAMERA_SOURCE in {"mock-video", "file", "video"}: return CAMERA_VIDEO_PATH
        if CAMERA_SOURCE == "usb": return CAMERA_USB_INDEX
        if CAMERA_SOURCE == "rtsp": return CAMERA_RTSP_URL
        raise ValueError("CAMERA_SOURCE must be mock-video, file, usb, or rtsp")

    def _open(self):
        import cv2
        if self.capture is not None: self.capture.release()
        target = self._target()
        if not target: raise RuntimeError("camera source is not configured")
        self.capture = cv2.VideoCapture(target)
        self.connected = bool(self.capture.isOpened())
        if not self.connected: raise RuntimeError(f"cannot open camera source: {CAMERA_SOURCE}")

    def read_jpeg(self) -> str | None:
        try:
            import cv2
            with self.lock:
                if self.capture is None or not self.capture.isOpened(): self._open()
                ok, frame = self.capture.read()
                if not ok and CAMERA_SOURCE in {"mock-video", "file", "video"}:
                    self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0); ok, frame = self.capture.read()
                if not ok: raise RuntimeError("camera returned no frame")
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, int(os.getenv("FRAME_JPEG_QUALITY", "85"))])
                if not ok: raise RuntimeError("failed to encode camera frame")
                self.latest_jpeg = encoded.tobytes(); self.frame_count += 1; self.latest_timestamp = datetime.now(UTC).isoformat(); self.connected, self.error = True, None
                return base64.b64encode(self.latest_jpeg).decode("ascii")
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.connected, self.error = False, str(error); logger.warning("camera_frame_failed source=%s error=%s", CAMERA_SOURCE, error); return None

    def status(self) -> dict[str, object]:
        return {"kind": CAMERA_SOURCE, "connected": self.connected, "latest_timestamp": self.latest_timestamp, "frame_count": self.frame_count, "error": self.error}

    def latest_frame(self) -> bytes | None:
        with self.lock:
            return self.latest_jpeg


class LatestFrameBuffer:
    """A capacity-one buffer: slow inference never causes a video backlog."""
    def __init__(self) -> None:
        self.lock = Lock()
        self.sequence = 0
        self.processed_sequence = 0
        self.frame: tuple[int, str, str, str] | None = None
        self.received_count = 0
        self.latest_timestamp = "waiting for first pushed frame"

    def put(self, frame_id: str, jpeg: bytes) -> None:
        with self.lock:
            self.sequence += 1
            self.received_count += 1
            self.latest_timestamp = datetime.now(UTC).isoformat()
            self.frame = (self.sequence, frame_id, base64.b64encode(jpeg).decode("ascii"), self.latest_timestamp)

    def take_latest(self) -> tuple[str, str, str] | None:
        with self.lock:
            if self.frame is None or self.frame[0] == self.processed_sequence:
                return None
            sequence, frame_id, jpeg, received_at = self.frame
            self.processed_sequence = sequence
            return frame_id, jpeg, received_at

    def status(self) -> dict[str, object]:
        with self.lock:
            return {"kind": "push", "connected": self.frame is not None, "latest_timestamp": self.latest_timestamp, "received_count": self.received_count, "pending": self.frame is not None and self.frame[0] != self.processed_sequence}

class TrackStore:
    def __init__(self) -> None: self.items: dict[str, tuple[str, list[float]]] = {}; self.counter = 0
    @staticmethod
    def _iou(a: list[float], b: list[float]) -> float:
        ax, ay, aw, ah = a; bx, by, bw, bh = b
        left, top, right, bottom = max(ax, bx), max(ay, by), min(ax + aw, bx + bw), min(ay + ah, by + bh)
        overlap = max(0., right-left) * max(0., bottom-top)
        return overlap / max(1e-6, aw*ah + bw*bh - overlap)
    def key(self, label: str, box: list[float]) -> str:
        for key, (saved_label, saved_box) in self.items.items():
            if saved_label == label and self._iou(saved_box, box) >= .35: self.items[key] = (label, box); return key
        self.counter += 1; key = f"{label.lower().replace(' ', '-')}-{self.counter}"; self.items[key] = (label, box); return key


video_source, pushed_frames, tracks = VideoFrameSource(), LatestFrameBuffer(), TrackStore()
stop_event, worker, last_stages = Event(), None, {}
app = FastAPI(title="Where Is It Vision Orchestrator", version="0.2.0")


def call(stage: str, request_id: str, jpeg: str, payload: dict[str, object]) -> dict[str, object] | None:
    request = InferenceRequest(request_id=request_id, contract_version=CONTRACT_VERSION, deadline_ms=int(os.getenv("VISION_STAGE_TIMEOUT_MS", "8000")), source=f"camera:{CAMERA_SOURCE}", frame_ref=MediaReference(uri="file:///camera-frame.jpg", media_type="image/jpeg"), payload={"frame_jpeg_b64": jpeg, **payload})
    try:
        response = InternalServiceClient(STAGE_URLS[stage], stage).infer(request); last_stages[stage] = response.status.value
        return response.result if response.status == InferenceStatus.OK else None
    except ServiceCallError as error:
        last_stages[stage] = error.code.value; logger.warning("vision_stage_degraded request_id=%s stage=%s code=%s", request_id, stage, error.code.value); return None


def run_pipeline(jpeg: str | None = None, frame_id: str | None = None, observed_at: str | None = None) -> dict[str, object] | None:
    jpeg = jpeg or video_source.read_jpeg()
    if not jpeg: return None
    request_id = uuid.uuid4().hex
    florence = call("florence", request_id, jpeg, {"task": "<OD>"})
    if florence is None: return None
    candidates = [str(item.get("label")) for item in florence.get("detections", []) if isinstance(item, dict)] or PROMPTS
    grounding = call("grounding", request_id, jpeg, {"candidates": candidates})
    if grounding is None: return None
    detections = [item for item in grounding.get("detections", []) if isinstance(item, dict)]
    segmentation = call("sam", request_id, jpeg, {"detections": detections})
    if segmentation is None: return None
    segments = [item for item in segmentation.get("segments", []) if isinstance(item, dict) and float(item.get("mask_area", 0)) > 0]
    embeddings = call("embedding", request_id, jpeg, {"detections": segments})
    if embeddings is None: return None
    observed_at = observed_at or datetime.now(UTC).isoformat()
    observations = []
    for item in segments:
        label, box, confidence = str(item.get("label", "object")), item.get("box"), float(item.get("confidence", 0))
        if not isinstance(box, list) or len(box) != 4: continue
        observations.append({"track_key": tracks.key(label, box), "name": label, "system_name": label, "category": label, "aliases": [], "location_name": "camera view", "relation": "detected in current frame", "bounding_box": box, "confidence": confidence})
    if not observations: return None
    return {"source": "push" if VISION_ROLE == "receiver" else CAMERA_SOURCE, "frame_id": frame_id or f"{CAMERA_SOURCE}-{video_source.frame_count}", "observed_at": observed_at, "frame_image_b64": jpeg, "observations": observations}


def publish_batch(batch: dict[str, object]) -> bool:
    request = Request(f"{API_URL}/internal/observations/batch", data=json.dumps(batch).encode("utf-8"), headers={"Content-Type": "application/json", "X-Request-ID": uuid.uuid4().hex}, method="POST")
    try:
        with urlopen(request, timeout=5) as response: response.read()
        logger.info("observation_batch_published frame_id=%s", batch["frame_id"]); return True
    except OSError as error:
        logger.warning("observation_publish_failed error=%s", error); return False


def push_once() -> bool:
    if not VISION_INGEST_URL:
        logger.warning("vision_push_skipped reason=VISION_INGEST_URL_not_configured"); return False
    jpeg_b64 = video_source.read_jpeg()
    if not jpeg_b64: return False
    jpeg = base64.b64decode(jpeg_b64)
    frame_id = f"{CAMERA_SOURCE}-{video_source.frame_count}"
    headers = {"Content-Type": "image/jpeg", "X-Frame-ID": frame_id, "X-Request-ID": uuid.uuid4().hex}
    if VISION_PUSH_TOKEN: headers["X-Vision-Push-Token"] = VISION_PUSH_TOKEN
    request = Request(VISION_INGEST_URL, data=jpeg, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=VISION_PUSH_TIMEOUT_SECONDS) as response: response.read()
        logger.info("vision_frame_pushed frame_id=%s target=%s", frame_id, VISION_INGEST_URL); return True
    except OSError as error:
        logger.warning("vision_push_failed frame_id=%s error=%s", frame_id, error); return False


def process_pushed_frame_once() -> bool:
    frame = pushed_frames.take_latest()
    if frame is None: return False
    frame_id, jpeg, received_at = frame
    batch = run_pipeline(jpeg=jpeg, frame_id=frame_id, observed_at=received_at)
    return batch is not None and publish_batch(batch)

def publish_loop() -> None:
    while not stop_event.is_set():
        if VISION_ROLE == "pusher":
            push_once()
        else:
            process_pushed_frame_once()
        stop_event.wait(0.05 if VISION_ROLE == "receiver" else INTERVAL_SECONDS)


@app.on_event("startup")
def start_worker() -> None:
    global worker
    stop_event.clear(); worker = Thread(target=publish_loop, name="vision-orchestrator", daemon=True); worker.start()


@app.on_event("shutdown")
def stop_worker() -> None:
    stop_event.set()
    if worker: worker.join(timeout=2)


@app.get("/health/live")
def live() -> dict[str, str]: return {"status": "ok", "service": "vision-orchestrator"}


@app.get("/health/ready")
def ready() -> dict[str, object]:
    if VISION_ROLE == "receiver":
        source, source_ready = pushed_frames.status(), True
    else:
        source = video_source.status()
        source_ready = video_source.connected or (CAMERA_SOURCE in {"mock-video", "file", "video"} and Path(CAMERA_VIDEO_PATH).is_file())
    return {"status": "ready" if source_ready else "not_ready", "role": VISION_ROLE, "source": source, "stages": last_stages}


@app.post("/v1/frames")
async def receive_frame(request: FastAPIRequest, response: Response) -> dict[str, object]:
    if VISION_ROLE != "receiver": raise HTTPException(status_code=409, detail="VISION_ROLE must be receiver to accept pushed frames")
    if VISION_PUSH_TOKEN and not hmac.compare_digest(request.headers.get("X-Vision-Push-Token", ""), VISION_PUSH_TOKEN):
        raise HTTPException(status_code=401, detail="invalid push token")
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "image/jpeg":
        raise HTTPException(status_code=415, detail="content type must be image/jpeg")
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > VISION_PUSH_MAX_FRAME_BYTES:
        raise HTTPException(status_code=413, detail="frame exceeds the configured size limit")
    jpeg = await request.body()
    if not jpeg or len(jpeg) > VISION_PUSH_MAX_FRAME_BYTES or not jpeg.startswith(b"\xff\xd8"):
        raise HTTPException(status_code=422, detail="body must be a JPEG within the configured size limit")
    frame_id = request.headers.get("X-Frame-ID", uuid.uuid4().hex)
    pushed_frames.put(frame_id, jpeg)
    response.status_code = status.HTTP_202_ACCEPTED
    return {"accepted": True, "frame_id": frame_id, "queued": "latest"}


@app.post("/v1/frames/process")
def process_frame() -> dict[str, object]:
    accepted = push_once() if VISION_ROLE == "pusher" else process_pushed_frame_once()
    count = pushed_frames.status()["received_count"] if VISION_ROLE == "receiver" else video_source.frame_count
    return {"accepted": accepted, "role": VISION_ROLE, "stages": last_stages, "frame_id": count}


@app.get("/internal/camera/status")
def camera_status() -> dict[str, object]:
    source = pushed_frames.status() if VISION_ROLE == "receiver" else video_source.status()
    return {"active_source": "push" if VISION_ROLE == "receiver" else CAMERA_SOURCE, "role": VISION_ROLE, "sources": {"push" if VISION_ROLE == "receiver" else CAMERA_SOURCE: source}, "stages": last_stages}


@app.get("/api/camera/latest.jpg")
def latest_camera_frame():
    frame = video_source.latest_frame()
    if frame is None:
        raise HTTPException(status_code=404, detail="no captured frame is available yet")
    return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})