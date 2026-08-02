from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = ROOT / "services" / "vision-orchestrator"
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
if str(SERVICE_ROOT) not in sys.path: sys.path.insert(0, str(SERVICE_ROOT))

from app import main
from services.shared.client import ServiceCallError
from services.shared.contracts import ErrorCode, InferenceResponse, InferenceStatus


class PipelineTests(unittest.TestCase):
    def setUp(self):
        main.last_stages.clear()

    @staticmethod
    def success(_client, request):
        data = {
            "florence": {"detections": [{"label": "keys", "box": [.2, .3, .1, .1], "confidence": .5}]},
            "grounding": {"detections": [{"label": "keys", "box": [.2, .3, .1, .1], "confidence": .9}], "verified": True},
            "sam": {"segments": [{"label": "keys", "box": [.2, .3, .1, .1], "confidence": .9, "mask_area": .05}]},
            "embedding": {"embeddings": []},
        }
        return InferenceResponse(request_id=request.request_id, model_name=_client.name, model_version="test", status=InferenceStatus.OK, result=data[_client.name])

    def test_real_pipeline_only_publishes_verified_segment(self):
        with patch.object(main.video_source, "read_jpeg", return_value="ZmFrZQ=="), patch.object(main.InternalServiceClient, "infer", self.success):
            batch = main.run_pipeline()
        self.assertIsNotNone(batch)
        self.assertEqual(batch["observations"][0]["track_key"].split("-")[0], "keys")
        self.assertEqual(set(main.last_stages.values()), {"ok"})

    def test_timeout_stops_unverified_observation(self):
        with patch.object(main.video_source, "read_jpeg", return_value="ZmFrZQ=="), patch.object(main.InternalServiceClient, "infer", side_effect=ServiceCallError(ErrorCode.DEADLINE_EXCEEDED, "timeout")):
            self.assertIsNone(main.run_pipeline())
        self.assertIn("deadline_exceeded", main.last_stages.values())

    def test_contract_mismatch_stops_unverified_observation(self):
        with patch.object(main.video_source, "read_jpeg", return_value="ZmFrZQ=="), patch.object(main.InternalServiceClient, "infer", side_effect=ServiceCallError(ErrorCode.CONTRACT_MISMATCH, "bad version", False)):
            self.assertIsNone(main.run_pipeline())
        self.assertIn("contract_mismatch", main.last_stages.values())
