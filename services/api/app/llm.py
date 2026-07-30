from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import Settings
from .models import ObjectState, QueryResult


@dataclass
class AnswerComposer:
    settings: Settings

    def compose(self, result: QueryResult) -> tuple[str, float]:
        fallback = result.answer
        if not self.settings.deepseek_api_key or result.object is None:
            return fallback, 0.0
        facts = {
            "object_name": result.object.name,
            "status": result.status,
            "current_location": result.object.current_location.name if result.object.current_location else None,
            "last_location": result.object.last_location.name if result.object.last_location else None,
        }
        prompt = "Return only JSON {\\\"answer\\\": \\\"...\\\"}. Use only the supplied facts and do not invent values.\\n" + json.dumps(facts, ensure_ascii=False)
        payload = json.dumps({"model": self.settings.deepseek_model, "messages": [{"role": "user", "content": prompt}], "response_format": {"type": "json_object"}, "temperature": 0.1}).encode("utf-8")
        request = Request(
            f"{self.settings.deepseek_base_url}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.llm_timeout_seconds) as response:
                answer = str(json.loads(json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"]).get("answer", "")).strip()
        except (KeyError, TypeError, ValueError, URLError, TimeoutError, OSError):
            return fallback, 0.0
        if self._is_safe(answer, result):
            return answer, 0.0
        return fallback, 0.0

    @staticmethod
    def _is_safe(answer: str, result: QueryResult) -> bool:
        if not answer or not result.object or result.object.name not in answer:
            return False
        if result.status == ObjectState.CURRENTLY_DETECTED:
            return bool(result.object.current_location and result.object.current_location.name in answer)
        if "\u5f53\u524d\u672a\u68c0\u6d4b" not in answer:

            return False
        return not result.object.last_location or result.object.last_location.name in answer
