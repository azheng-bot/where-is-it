from __future__ import annotations

import asyncio
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = ROOT / "services" / "vision-orchestrator"
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
if str(SERVICE_ROOT) not in sys.path: sys.path.insert(0, str(SERVICE_ROOT))

from fastapi import Response
from app import main


class FakeRequest:
    def __init__(self, body: bytes, headers: dict[str, str]) -> None:
        self._body, self.headers = body, headers

    async def body(self) -> bytes:
        return self._body


class PushTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        main.pushed_frames = main.LatestFrameBuffer()

    def test_latest_buffer_discards_stale_frame(self):
        main.pushed_frames.put("frame-1", b"\xff\xd8one")
        main.pushed_frames.put("frame-2", b"\xff\xd8two")
        frame = main.pushed_frames.take_latest()
        self.assertIsNotNone(frame)
        self.assertEqual(frame[0], "frame-2")
        self.assertEqual(base64.b64decode(frame[1]), b"\xff\xd8two")
        self.assertIsNone(main.pushed_frames.take_latest())

    def test_receiver_accepts_jpeg_with_matching_token(self):
        request = FakeRequest(b"\xff\xd8jpeg", {"content-type": "image/jpeg", "X-Frame-ID": "remote-1", "X-Vision-Push-Token": "secret"})
        with patch.object(main, "VISION_ROLE", "receiver"), patch.object(main, "VISION_PUSH_TOKEN", "secret"):
            response = Response()
            result = asyncio.run(main.receive_frame(request, response))
        self.assertEqual(response.status_code, 202)
        self.assertEqual(result["frame_id"], "remote-1")
        self.assertEqual(main.pushed_frames.take_latest()[0], "remote-1")

    def test_pusher_posts_raw_jpeg_to_configured_receiver(self):
        fake_response = MagicMock()
        fake_response.__enter__.return_value = fake_response
        with patch.object(main.video_source, "read_jpeg", return_value=base64.b64encode(b"\xff\xd8jpeg").decode("ascii")), patch.object(main.video_source, "frame_count", 7), patch.object(main, "VISION_INGEST_URL", "http://203.0.113.10:8001/v1/frames"), patch.object(main, "VISION_PUSH_TOKEN", "secret"), patch.object(main, "urlopen", return_value=fake_response) as sender:
            self.assertTrue(main.push_once())
        request = sender.call_args.args[0]
        self.assertEqual(request.full_url, "http://203.0.113.10:8001/v1/frames")
        self.assertEqual(request.data, b"\xff\xd8jpeg")
        self.assertEqual(request.get_header("X-vision-push-token"), "secret")


if __name__ == "__main__":
    unittest.main()