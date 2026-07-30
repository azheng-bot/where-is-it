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
from services.shared.client import ServiceCallError
from services.shared.contracts import ErrorCode, InferenceResponse, InferenceStatus

class PipelineTests(unittest.TestCase):
    def setUp(self):
        main.last_stages.clear()

    def test_real_pipeline_accepts_only_verified_stage_results(self):
        def inference(_self, request):
            return InferenceResponse(request_id=request.request_id, model_name="model", model_version="mock-v1", status=InferenceStatus.OK)
        with patch.object(main, "VISION_MODE", "remote"), patch.object(main.InternalServiceClient, "infer", inference):
            batch = main.run_pipeline()
        self.assertIsNotNone(batch)
        self.assertEqual(set(main.last_stages.values()), {"ok"})

    def test_timeout_stops_unverified_observation(self):
        with patch.object(main, "VISION_MODE", "remote"), patch.object(main.InternalServiceClient, "infer", side_effect=ServiceCallError(ErrorCode.DEADLINE_EXCEEDED, "timeout")):
            batch = main.run_pipeline()
        self.assertIsNone(batch)
        self.assertIn("deadline_exceeded", main.last_stages.values())

    def test_contract_mismatch_stops_unverified_observation(self):
        with patch.object(main, "VISION_MODE", "remote"), patch.object(main.InternalServiceClient, "infer", side_effect=ServiceCallError(ErrorCode.CONTRACT_MISMATCH, "bad version", False)):
            batch = main.run_pipeline()
        self.assertIsNone(batch)
        self.assertIn("contract_mismatch", main.last_stages.values())