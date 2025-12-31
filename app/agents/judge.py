from __future__ import annotations

from typing import Dict, List

from ..utilities.errors import LLMError
from ..schemas.game import JudgeResult
from ..services.llm_client import LLMClient
from .prompts import build_judge_prompt


class JudgeAgent:
    def __init__(self, llm: LLMClient, model: str) -> None:
        self._llm = llm
        self._model = model

    def evaluate(
        self,
        session_memory: str,
        history_messages: List[Dict[str, str]],
        user_message: str,
    ) -> JudgeResult:
        prompt = build_judge_prompt(session_memory)
        transcript = self._format_transcript(history_messages)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    "RECENT CONVERSATION TRANSCRIPT:\n"
                    f"{transcript}\n\n"
                    "LATEST USER MESSAGE:\n"
                    f"{user_message}"
                ),
            },
        ]

        payload = self._llm.chat_json(
            self._model,
            messages,
            retry_hint=(
                "Return ONLY valid JSON matching this schema:\n"
                '{"reasoning":"...","score":0}\n'
                "Rules: allowed scores are -20, -10, 0, 5, 10, 20. No extra text."
            ),
            temperature=0.0,
            max_tokens=250,
        )

        try:
            return JudgeResult.model_validate(payload)
        except Exception as exc:
            raise LLMError("Judge returned invalid JSON structure.") from exc

    @staticmethod
    def _format_transcript(history_messages: List[Dict[str, str]]) -> str:
        if not history_messages:
            return "(none)"
        lines: List[str] = []
        for message in history_messages:
            role = message.get("role")
            speaker = "Viktor" if role == "assistant" else "User"
            content = message.get("content", "")
            lines.append(f"{speaker}: {content}")
        return "\n".join(lines)
