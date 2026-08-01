from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.shared.client import InternalServiceClient, ServiceCallError
from services.shared.contracts import CONTRACT_VERSION, ErrorCode, InferenceRequest, MediaReference

class InternalContractTests(unittest.TestCase):
    def request(self) -> InferenceRequest:
        return InferenceRequest(request_id="request-1", contract_version=CONTRACT_VERSION, deadline_ms=50, source="test", frame_ref=MediaReference(uri="file:///fixture.png"))

    def test_missing_media_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            InferenceRequest(request_id="request-1", deadline_ms=50, source="test")

    def test_unconfigured_service_is_distinguishable(self):
        with self.assertRaises(ServiceCallError) as caught:
            InternalServiceClient("", "test-service").infer(self.request())
        self.assertEqual(caught.exception.code, ErrorCode.SERVICE_UNAVAILABLE)
        self.assertFalse(caught.exception.retryable)

    @patch("services.shared.client.urlopen", side_effect=TimeoutError("expired"))
    def test_timeout_is_mapped_to_deadline_exceeded(self, _urlopen):
        with self.assertRaises(ServiceCallError) as caught:
            InternalServiceClient("http://127.0.0.1:9", "test-service").infer(self.request())
        self.assertEqual(caught.exception.code, ErrorCode.DEADLINE_EXCEEDED)