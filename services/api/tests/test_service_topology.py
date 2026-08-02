from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi import Response

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import ready


def health_response(status: str) -> MagicMock:
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps({"status": status}).encode("utf-8")
    return response


class GpuServiceHealthTests(unittest.TestCase):
    def test_ready_aggregates_vision_and_asr(self):
        with patch("app.main.urlopen", side_effect=[health_response("ready"), health_response("ready")]):
            response = Response()
            payload = ready(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["components"]["vision"]["status"], "ready")
        self.assertEqual(payload["components"]["asr"]["status"], "ready")

    def test_unavailable_vision_marks_gpu_service_not_ready(self):
        with patch("app.main.urlopen", side_effect=OSError("receiver offline")):
            response = Response()
            payload = ready(response)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["components"]["vision"]["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()