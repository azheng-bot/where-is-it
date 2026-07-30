from dataclasses import dataclass
from enum import StrEnum
from fastapi import FastAPI


class SourceKind(StrEnum):
    USB = "usb"
    RTSP = "rtsp"
    FIXTURE = "fixture"


@dataclass
class FrameSource:
    kind: SourceKind
    connected: bool = True
    latest_timestamp: str = "等待第一帧"

    def status(self) -> dict[str, str | bool]:
        return {"kind": self.kind, "connected": self.connected, "latest_timestamp": self.latest_timestamp}


class ModelAdapter:
    """Common readiness contract; concrete model integrations plug in here."""
    name = "base"

    def ready(self) -> bool:
        return True


class DetectorAdapter(ModelAdapter):
    name = "detector"


class CaptionerAdapter(ModelAdapter):
    name = "captioner"


class SegmentTrackerAdapter(ModelAdapter):
    name = "segment-tracker"


class EmbeddingAdapter(ModelAdapter):
    name = "embedding"


class OcrAdapter(ModelAdapter):
    name = "ocr"


sources = {kind: FrameSource(kind) for kind in SourceKind}
adapters = [DetectorAdapter(), CaptionerAdapter(), SegmentTrackerAdapter(), EmbeddingAdapter(), OcrAdapter()]
app = FastAPI(title="Where Is It Vision", version="0.1.0")


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def ready() -> dict[str, object]:
    return {"status": "ready", "profile": "cpu-demo", "models": {adapter.name: adapter.ready() for adapter in adapters}}


@app.get("/internal/camera/status")
def camera_status() -> dict[str, object]:
    return {"active_source": SourceKind.FIXTURE, "sources": {kind: source.status() for kind, source in sources.items()}}
