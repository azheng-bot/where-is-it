from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
from urllib.request import Request, urlopen

from fastapi import FastAPI
from fastapi.responses import FileResponse

FIXTURE_PATH = Path(os.getenv("CAMERA_FIXTURE_PATH", Path(__file__).parents[1] / "fixtures" / "bedroom-mock.png")).resolve()
API_URL = os.getenv("API_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
INTERVAL_SECONDS = float(os.getenv("MOCK_FRAME_INTERVAL_SECONDS", "0.7"))

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
    latest_timestamp: str = "等待第一帧"
    frame_count: int = 0

    def batch(self) -> dict[str, object]:
        now = datetime.now(UTC)
        self.frame_count += 1
        self.latest_timestamp = now.isoformat()
        observations = []
        for key, name, system_name, category, aliases, location, relation, bbox, confidence in MOCK_OBJECTS:
            observations.append({"track_key": key, "name": name, "system_name": system_name, "category": category, "aliases": aliases, "location_name": location, "relation": relation, "bounding_box": bbox, "confidence": confidence})
        return {"source": "fixture", "frame_id": f"bedroom-mock-{self.frame_count}", "observed_at": self.latest_timestamp, "fixture_image_path": str(FIXTURE_PATH), "observations": observations}

    def status(self) -> dict[str, object]:
        return {"kind": "fixture", "connected": self.connected, "latest_timestamp": self.latest_timestamp, "frame_count": self.frame_count, "path": FIXTURE_PATH.name}

source = MockFrameSource()
stop_event = Event()
worker: Thread | None = None
app = FastAPI(title="Where Is It Vision", version="0.2.0")

def publish_loop() -> None:
    while not stop_event.is_set():
        source.connected = FIXTURE_PATH.is_file()
        if source.connected:
            request = Request(f"{API_URL}/internal/observations/batch", data=json.dumps(source.batch()).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urlopen(request, timeout=1.5):
                    pass
            except OSError:
                pass
        stop_event.wait(INTERVAL_SECONDS)

@app.on_event("startup")
def start_worker() -> None:
    global worker
    stop_event.clear()
    worker = Thread(target=publish_loop, name="mock-fixture-publisher", daemon=True)
    worker.start()

@app.on_event("shutdown")
def stop_worker() -> None:
    stop_event.set()
    if worker:
        worker.join(timeout=2)

@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/health/ready")
def ready() -> dict[str, object]:
    return {"status": "ready" if FIXTURE_PATH.is_file() else "not_ready", "profile": "fixture-mock", "models": {"mock-detector": True}, "fixture": source.status()}

@app.get("/internal/camera/status")
def camera_status() -> dict[str, object]:
    return {"active_source": "fixture", "sources": {"fixture": source.status()}}

@app.get("/api/camera/frame")
def camera_frame():
    if not FIXTURE_PATH.is_file():
        return {"detail": "mock frame missing"}
    return FileResponse(FIXTURE_PATH, media_type="image/png")