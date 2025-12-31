from __future__ import annotations

from ..utilities.errors import LLMError
from ..schemas.game import SessionMemory
from ..services.llm_client import LLMClient
from .prompts import build_compactor_prompt


class CompactorAgent:
    def __init__(self, llm: LLMClient, model: str) -> None:
        self._llm = llm
        self._model = model

    def compact(self, existing_memory: str, messages_to_compact: str) -> str:
        prompt = build_compactor_prompt(existing_memory, messages_to_compact)
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Update session memory."},
        ]

        payload = self._llm.chat_json(
            self._model,
            messages,
            retry_hint="Return ONLY valid JSON.",
            temperature=0.0,
            max_tokens=1600,
        )

        try:
            memory = SessionMemory.model_validate(payload)
        except Exception as exc:
            raise LLMError("Compactor returned invalid JSON structure.") from exc

        return memory.model_dump_json()
