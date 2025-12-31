from __future__ import annotations

from typing import Dict, List

from ..services.llm_client import LLMClient
from .prompts import build_doorman_prompt


class DoormanAgent:
    def __init__(self, llm: LLMClient, model: str) -> None:
        self._llm = llm
        self._model = model

    def respond(
        self,
        session_memory: str,
        history_messages: List[Dict[str, str]],
        user_message: str,
        directive: str,
    ) -> str:
        system_prompt = build_doorman_prompt(directive)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

        if session_memory:
            messages.append({"role": "system", "content": f"SESSION MEMORY:\n{session_memory}"})

        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_message})

        return self._llm.chat(self._model, messages, temperature=0.7)