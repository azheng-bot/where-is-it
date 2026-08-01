from __future__ import annotations

import base64
import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock, Thread
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from services.shared.client import InternalServiceClient, ServiceCallError
from services.shared.contracts import CONTRACT_VERSION, InferenceRequest, InferenceStatus, MediaReference

logger = logging.getLogger("vision-orchestrator")
FIXTURE_PATH = Path(os.getenv("CAMERA_FIXTURE_PATH", Path(__file__).parents[1] / "fixtures" / "bedroom-mock.png")).resolve()
MOCK_VIDEO_PATH = Path(os.getenv("CAMERA_MOCK_VIDEO_PATH", Path(__file__).parents[1] / "fixtures" / "media" / "indoor-living-room.mp4")).resolve()
CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "mock-video").lower()
CAMERA_VIDEO_PATH = os.getenv("CAMERA_VIDEO_PATH", str(MOCK_VIDEO_PATH))
CAMERA_USB_INDEX = int(os.getenv("CAMERA_USB_INDEX", "0"))
CAMERA_RTSP_URL = os.getenv("CAMERA_RTSP_URL", "")
API_URL = os.getenv("API_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
INTERVAL_SECONDS = float(os.getenv("DISCOVERY_INTERVAL_SECONDS", os.getenv("MOCK_FRAME_INTERVAL_SECONDS", "0.7")))
VISION_MODE = os.getenv("VISION_MODE", "mock").lower()
PROMPTS = [value.strip() for value in os.getenv("VISION_PROMPTS", "keys,glasses,mug,bottle,laptop,backpack,notebook,headphones,remote control,table lamp").split(",") if value.strip()]
STAGE_URLS = {"florence": os.getenv("FLORENCE_SERVICE_URL", "http://127.0.0.1:8002"), "grounding": os.getenv("GROUNDING_SERVICE_URL", "http://127.0.0.1:8003"), "sam": os.getenv("SAM_SERVICE_URL", "http://127.0.0.1:8004"), "embedding": os.getenv("EMBEDDING_SERVICE_URL", "http://127.0.0.1:8005")}

MOCK_OBJECTS = [
    ("tumbler-black", "黑色保温杯", "黑色保温杯", "水杯", ["保温杯", "水杯"], "书桌", "书桌左侧", (.12, .60, .06, .16), .98),
    ("mug-white", "白色马克杯", "白色马克杯", "水杯", ["马克杯", "杯子"], "书桌", "书桌中部", (.22, .62, .06, .10), .97),
    ("glasses", "黑框眼镜", "黑框眼镜", "眼镜", ["眼镜"], "书桌", "笔记本前方", (.24, .81, .07, .06), .95),
    ("keys", "我的钥匙", "银色钥匙", "钥匙", ["钥匙", "门钥匙"], "书桌", "书桌前侧", (.36, .84, .07, .07), .99),
    ("earbuds-case", "白色耳机盒", "白色耳机盒", "耳机", ["耳机", "耳机盒"], "书桌", "红色笔记本右侧", (.23, .92, .05, .05), .94),
    ("notebook-red", "红色笔记本", "红色笔记本", "文具", ["笔记本"], "书桌", "书桌左下角", (.07, .83, .12, .16), .96),
    ("lamp-black", "黑色台灯", "黑色台灯", "灯具", ["台灯"], "书桌", "书桌左侧", (.01, .43, .14, .30), .93),
    ("backpack-blue", "蓝色背包", "蓝色背包", "包", ["背包"], "地面", "衣柜前方", (.28, .37, .08, .15), .96),
    ("laptop-silver", "银色笔记本电脑", "银色笔记本电脑", "电脑", ["电脑", "笔记本电脑"], "书桌", "书桌中部", (.29, .68, .12, .16), .97),
    ("tissue-green", "绿色纸巾盒", "绿色纸巾盒", "纸巾", ["纸巾"], "右侧床头柜", "床头柜上方", (.86, .40, .08, .06), .92),
]


@dataclass
class MockFrameSource:
    connected: bool = True
    latest_timestamp: str = "waiting for first frame"
    frame_count: int = 0

    def batch(self) -> dict[str, object]:
        self.frame_count += 1; self.latest_timestamp = datetime.now(UTC).isoformat()
        observations = [{"track_key": key, "name": name, "system_name": system_name, "category": category, "aliases": aliases, "location_name": location, "relation": relation, "bounding_box": bbox, "confidence": confidence} for key, name, system_name, category, aliases, location, relation, bbox, confidence in MOCK_OBJECTS]
        return {"source": CAMERA_SOURCE, "frame_id": f"bedroom-mock-{self.frame_count}", "observed_at": self.latest_timestamp, "fixture_image_path": str(FIXTURE_PATH), "observations": observations}

    def status(self) -> dict[str, object]:
        return {"kind": CAMERA_SOURCE, "connected": self.connected, "latest_timestamp": self.latest_timestamp, "frame_count": self.frame_count, "poster_path": FIXTURE_PATH.name, "video_path": MOCK_VIDEO_PATH.name if MOCK_VIDEO_PATH.is_file() else None}


class VideoFrameSource:
    """Latest-frame capture for files, USB devices, and RTSP streams."""
    def __init__(self) -> None:
        self.capture = None; self.lock = Lock(); self.frame_count = 0; self.latest_timestamp = "waiting for first frame"; self.connected = False; self.error: str | None = None

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
                self.frame_count += 1; self.latest_timestamp = datetime.now(UTC).isoformat(); self.connected, self.error = True, None
                return base64.b64encode(encoded.tobytes()).decode("ascii")
        except (ImportError, OSError, RuntimeError, ValueError) as error:
            self.connected, self.error = False, str(error); logger.warning("camera_frame_failed source=%s error=%s", CAMERA_SOURCE, error); return None

    def status(self) -> dict[str, object]:
        return {"kind": CAMERA_SOURCE, "connected": self.connected, "latest_timestamp": self.latest_timestamp, "frame_count": self.frame_count, "error": self.error}


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


mock_source, video_source, tracks = MockFrameSource(), VideoFrameSource(), TrackStore()
stop_event, worker, last_stages = Event(), None, {}
app = FastAPI(title="Where Is It Vision Orchestrator", version="0.2.0")


def call(stage: str, request_id: str, jpeg: str, payload: dict[str, object]) -> dict[str, object] | None:
    request = InferenceRequest(request_id=request_id, contract_version=CONTRACT_VERSION, deadline_ms=int(os.getenv("VISION_STAGE_TIMEOUT_MS", "8000")), source=f"camera:{CAMERA_SOURCE}", frame_ref=MediaReference(uri="file:///camera-frame.jpg", media_type="image/jpeg"), payload={"frame_jpeg_b64": jpeg, **payload})
    try:
        response = InternalServiceClient(STAGE_URLS[stage], stage).infer(request); last_stages[stage] = response.status.value
        return response.result if response.status == InferenceStatus.OK else None
    except ServiceCallError as error:
        last_stages[stage] = error.code.value; logger.warning("vision_stage_degraded request_id=%s stage=%s code=%s", request_id, stage, error.code.value); return None


def run_pipeline() -> dict[str, object] | None:
    if VISION_MODE == "mock":
        last_stages.update({name: "mock" for name in STAGE_URLS}); return mock_source.batch()
    jpeg = video_source.read_jpeg()
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
    observed_at = datetime.now(UTC).isoformat()
    observations = []
    for item in segments:
        label, box, confidence = str(item.get("label", "object")), item.get("box"), float(item.get("confidence", 0))
        if not isinstance(box, list) or len(box) != 4: continue
        observations.append({"track_key": tracks.key(label, box), "name": label, "system_name": label, "category": label, "aliases": [], "location_name": "camera view", "relation": "detected in current frame", "bounding_box": box, "confidence": confidence})
    if not observations: return None
    return {"source": CAMERA_SOURCE, "frame_id": f"{CAMERA_SOURCE}-{video_source.frame_count}", "observed_at": observed_at, "frame_image_b64": jpeg, "observations": observations}


def publish_once() -> bool:
    if VISION_MODE == "mock": mock_source.connected = FIXTURE_PATH.is_file()
    batch = run_pipeline()
    if batch is None: return False
    request = Request(f"{API_URL}/internal/observations/batch", data=json.dumps(batch).encode("utf-8"), headers={"Content-Type": "application/json", "X-Request-ID": uuid.uuid4().hex}, method="POST")
    try:
        with urlopen(request, timeout=5) as response: response.read()
        logger.info("observation_batch_published frame_id=%s mode=%s", batch["frame_id"], VISION_MODE); return True
    except OSError as error:
        logger.warning("observation_publish_failed error=%s", error); return False


def publish_loop() -> None:
    while not stop_event.is_set(): publish_once(); stop_event.wait(INTERVAL_SECONDS)


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
    source_ready = FIXTURE_PATH.is_file() if VISION_MODE == "mock" else video_source.connected
    return {"status": "ready" if source_ready else "not_ready", "mode": VISION_MODE, "fixture": mock_source.status() if VISION_MODE == "mock" else video_source.status(), "stages": last_stages}


@app.post("/v1/frames/process")
def process_frame() -> dict[str, object]:
    accepted = publish_once(); count = mock_source.frame_count if VISION_MODE == "mock" else video_source.frame_count
    return {"accepted": accepted, "mode": VISION_MODE, "stages": last_stages, "frame_id": count}


@app.get("/internal/camera/status")
def camera_status() -> dict[str, object]: return {"active_source": CAMERA_SOURCE, "sources": {CAMERA_SOURCE: mock_source.status() if VISION_MODE == "mock" else video_source.status()}, "stages": last_stages}


@app.get("/api/camera/frame")
def camera_frame():
    if not FIXTURE_PATH.is_file(): raise HTTPException(status_code=404, detail="camera poster missing")
    return FileResponse(FIXTURE_PATH, media_type="image/png")


@app.get("/api/camera/stream")
def camera_stream():
    if CAMERA_SOURCE != "mock-video" or not MOCK_VIDEO_PATH.is_file(): raise HTTPException(status_code=404, detail="a browser stream is only available for the bundled mock video")
    return FileResponse(MOCK_VIDEO_PATH, media_type="video/mp4", filename="camera-live.mp4")
