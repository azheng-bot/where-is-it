from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.asr.app.main import AsrSettings, FasterWhisperAdapter, TranscriptionError, TranscriptionService


class AsrServiceTests(unittest.TestCase):
    def test_mock_mode_returns_chinese_text_and_accepts_codec_parameter(self) -> None:
        result = TranscriptionService(AsrSettings(mode="mock")).transcribe(b"audio-fixture", "audio/webm;codecs=opus")
        self.assertEqual(result.text, "我的钥匙在哪里？")
        self.assertEqual(result.language, "zh")
        self.assertEqual(result.provider, "mock-asr")

    def test_rejects_unsupported_empty_and_oversized_audio(self) -> None:
        service = TranscriptionService(AsrSettings(mode="mock", max_audio_bytes=4))
        with self.assertRaisesRegex(TranscriptionError, "Unsupported audio type") as unsupported:
            service.transcribe(b"audio", "text/plain")
        self.assertEqual((unsupported.exception.code, unsupported.exception.status_code), ("unsupported_media_type", 415))
        with self.assertRaises(TranscriptionError) as empty:
            service.transcribe(b"", "audio/webm")
        self.assertEqual(empty.exception.code, "empty_audio")
        with self.assertRaises(TranscriptionError) as oversized:
            service.transcribe(b"audio", "audio/webm")
        self.assertEqual(oversized.exception.code, "audio_too_large")

    def test_disabled_service_is_explicitly_unavailable(self) -> None:
        service = TranscriptionService(AsrSettings(mode="mock", ready_override=False))
        with self.assertRaises(TranscriptionError) as unavailable:
            service.transcribe(b"audio", "audio/webm")
        self.assertEqual((unavailable.exception.code, unavailable.exception.status_code), ("model_not_ready", 503))

    def test_faster_whisper_adapter_uses_chinese_transcription_options(self) -> None:
        calls: dict[str, object] = {}
        class FakeModel:
            def transcribe(self, path: str, **kwargs: object):
                calls["path"] = path
                calls["options"] = kwargs
                return iter([SimpleNamespace(text=" 我的钥匙在哪里？", avg_logprob=-0.1)]), SimpleNamespace(language="zh")
        def fake_factory(model: str, **kwargs: object) -> FakeModel:
            calls["model"] = model
            calls["model_options"] = kwargs
            return FakeModel()
        result = FasterWhisperAdapter(AsrSettings(mode="faster-whisper"), model_factory=fake_factory).transcribe(b"fixture", "audio/wav")
        self.assertEqual(result.text, "我的钥匙在哪里？")
        self.assertEqual(result.provider, "faster-whisper")
        self.assertEqual(calls["model_options"], {"device": "cpu", "compute_type": "int8"})
        self.assertEqual(calls["options"], {"language": "zh", "task": "transcribe", "beam_size": 5, "vad_filter": True, "condition_on_previous_text": False})
        self.assertFalse(Path(str(calls["path"])).exists())

    def test_empty_faster_whisper_result_is_not_reported_as_success(self) -> None:
        class EmptyModel:
            def transcribe(self, path: str, **kwargs: object):
                return iter([SimpleNamespace(text="", avg_logprob=None)]), SimpleNamespace(language="zh")
        adapter = FasterWhisperAdapter(AsrSettings(mode="faster-whisper"), model_factory=lambda *args, **kwargs: EmptyModel())
        with self.assertRaises(TranscriptionError) as error:
            adapter.transcribe(b"fixture", "audio/webm")
        self.assertEqual(error.exception.code, "empty_transcription")


if __name__ == "__main__":
    unittest.main()
