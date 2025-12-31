from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from openai import OpenAI

from ..config.settings import get_settings
from ..utilities.errors import LLMError


class LLMClient:
    def __init__(self, client: OpenAI, json_max_retries: int = 1) -> None:
        self._client = client
        self._json_max_retries = max(0, json_max_retries)
        self._logger = logging.getLogger("doorman-game")

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        try:
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            return content or ""
        except Exception as exc:
            self._logger.error("LLM request failed for model %s: %s", model, exc, exc_info=True)
            raise LLMError("LLM request failed.", {"model": model, "error": str(exc)}) from exc

    def chat_json(
        self,
        model: str,
        messages: List[Dict[str, str]],
        retry_hint: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        max_retries: int | None = None,
        allow_repair: bool = False,
    ) -> Dict[str, Any]:
        if max_retries is None:
            max_retries = self._json_max_retries
        current_messages = messages
        current_temperature = temperature
        last_content = ""

        for attempt in range(max_retries + 1):
            try:
                content = self.chat(
                    model=model,
                    messages=current_messages,
                    temperature=current_temperature,
                    max_tokens=max_tokens,
                )
            except LLMError:
                if attempt >= max_retries:
                    raise
                continue

            last_content = content
            parsed, repaired = self._try_parse_json_object(content, allow_repair=allow_repair)
            if parsed is not None:
                if repaired:
                    self._logger.warning(
                        "Minor JSON repair applied for model %s. Response: %s",
                        model,
                        self._truncate(content),
                    )
                return parsed

            self._logger.warning(
                "Invalid JSON from model %s (attempt %s/%s). Response: %s",
                model,
                attempt + 1,
                max_retries + 1,
                self._truncate(content),
            )
            current_messages = messages + [
                {"role": "system", "content": retry_hint},
                {"role": "system", "content": "Return a single JSON object and nothing else."},
            ]
            current_temperature = 0.0

        raise LLMError(
            "LLM returned invalid JSON.",
            {"model": model, "response": self._truncate(last_content)},
        )

    @staticmethod
    def _try_parse_json_object(raw: str, *, allow_repair: bool) -> tuple[Optional[Dict[str, Any]], bool]:
        parsed = LLMClient._loads_json_object(raw)
        if parsed is not None:
            return parsed, False

        if not allow_repair:
            return None, False

        repaired = LLMClient._repair_json_text(raw)
        if repaired is None or repaired == raw:
            return None, False

        parsed = LLMClient._loads_json_object(repaired)
        if parsed is not None:
            return parsed, True
        return None, False

    @staticmethod
    def _loads_json_object(raw: str) -> Optional[Dict[str, Any]]:
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict):
            return None
        return value

    @staticmethod
    def _repair_json_text(raw: str) -> Optional[str]:
        text = raw.strip()
        if not text:
            return None

        if "```" in text:
            text = text.replace("```", "")

        start = text.find("{")
        if start == -1:
            return None
        text = text[start:]

        text = LLMClient._extract_first_json_object_or_prefix(text)
        text = LLMClient._remove_trailing_commas(text)
        text = LLMClient._balance_brackets(text)
        return text.strip()

    @staticmethod
    def _extract_first_json_object_or_prefix(text: str) -> str:
        stack: List[str] = []
        in_string = False
        escape = False

        for idx, ch in enumerate(text):
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in ("}", "]"):
                if stack and ch == stack[-1]:
                    stack.pop()
                else:
                    return text

            if idx > 0 and not stack:
                return text[: idx + 1]

        return text

    @staticmethod
    def _balance_brackets(text: str) -> str:
        stack: List[str] = []
        in_string = False
        escape = False

        for ch in text:
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue

            if ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in ("}", "]"):
                if stack and ch == stack[-1]:
                    stack.pop()
                else:
                    return text

        if not stack:
            return text
        return text + "".join(reversed(stack))

    @staticmethod
    def _remove_trailing_commas(text: str) -> str:
        previous = None
        current = text
        while previous != current:
            previous = current
            current = re.sub(r",(\s*[}\]])", r"\1", current)
        return current

    @staticmethod
    def _truncate(text: str, limit: int = 600) -> str:
        cleaned = text.replace("\r", " ").replace("\n", " ").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[:limit] + "...(truncated)"


@lru_cache(maxsize=1)
def get_llm_client() -> LLMClient:
    settings = get_settings()
    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
    )
    return LLMClient(client, json_max_retries=settings.llm_json_retries)
