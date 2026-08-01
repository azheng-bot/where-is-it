from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from starlette.datastructures import Headers, UploadFile

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.asr import AsrServiceError, AsrServiceResult
from app.main import transcribe


def audio_file(content_type: str = "audio/webm") -> UploadFile:
    return UploadFile(file=BytesIO(b"audio-fixture"), filename="question.webm", headers=Headers({"content-type": content_type}))

class AsrApiTests(unittest.TestCase):
    def test_successful_transcription_returns_text(self):
        with patch("app.main.AsrClient.transcribe", return_value=AsrServiceResult("where are my keys", "mock-asr", "mock-v1")):
            result = asyncio.run(transcribe(audio_file()))
        self.assertEqual(result.status, "success")
        self.assertEqual(result.text, "where are my keys")

    def test_asr_failure_does_not_return_guessed_text(self):
        with patch("app.main.AsrClient.transcribe", side_effect=AsrServiceError("deadline_exceeded", "timeout")):
            result = asyncio.run(transcribe(audio_file()))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.error_code, "deadline_exceeded")
        self.assertEqual(result.text, "")

    def test_unconfigured_asr_is_distinguishable(self):
        from app.asr import AsrClient
        with self.assertRaises(AsrServiceError) as caught:
            AsrClient("", 1).transcribe(b"audio", "audio/webm")
        self.assertEqual(caught.exception.code, "asr_not_configured")
    def test_keyboard_query_endpoint_is_not_coupled_to_asr_client(self):
        from app.main import query
        from app.models import QueryRequest
        with patch("app.main.AsrClient.transcribe", side_effect=AssertionError("keyboard query must not call ASR")):
            result = query(QueryRequest(text="keys"))
        self.assertIsNotNone(result)