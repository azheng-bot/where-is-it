from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = ROOT / "services" / "vision-orchestrator"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app import main


class VideoStreamerConfigurationTests(unittest.TestCase):
    def test_supported_sources_resolve_without_model_or_database_configuration(self):
        with patch.object(main, "CAMERA_SOURCE", "mock-video"), patch.object(main, "CAMERA_VIDEO_PATH", "fixture.mp4"):
            self.assertEqual(main.VideoFrameSource()._target(), "fixture.mp4")
        with patch.object(main, "CAMERA_SOURCE", "usb"), patch.object(main, "CAMERA_USB_INDEX", 3):
            self.assertEqual(main.VideoFrameSource()._target(), 3)
        with patch.object(main, "CAMERA_SOURCE", "rtsp"), patch.object(main, "CAMERA_RTSP_URL", "rtsp://camera.example/stream"):
            self.assertEqual(main.VideoFrameSource()._target(), "rtsp://camera.example/stream")

    def test_pusher_failure_drops_the_current_frame(self):
        with patch.object(main.video_source, "read_jpeg", return_value="/9hqdXBlZw=="), patch.object(main.video_source, "frame_count", 1), patch.object(main, "VISION_INGEST_URL", "http://127.0.0.1:9/v1/frames"), patch.object(main, "urlopen", side_effect=OSError("receiver offline")):
            self.assertFalse(main.push_once())
        self.assertIsNone(main.pushed_frames.take_latest())


if __name__ == "__main__":
    unittest.main()