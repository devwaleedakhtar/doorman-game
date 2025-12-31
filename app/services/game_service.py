from __future__ import annotations

import logging
import re
import uuid
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from ..agents.compactor import CompactorAgent
from ..agents.doorman import DoormanAgent
from ..agents.judge import JudgeAgent
from ..agents.prompts import OPENING_LINE
from ..config.settings import Settings
from ..models.db_models import MessageModel, SessionModel
from ..utilities.errors import ConflictError, LLMError, NotFoundError, ValidationError
from ..schemas.game import (
    GameState,
    GameStatusResponse,
    MessageHistoryItem,
    MessageRole,
    SendMessageRequest,
    SendMessageResponse,
    SessionHistoryResponse,
    SessionMemory,
    StartGameResponse,
)
from ..repositories.game_repository import GameRepository
from .state_manager import StateManager
from .llm_client import LLMClient


class GameService:
    def __init__(self, settings: Settings, repo: GameRepository, llm_client: LLMClient) -> None:
        self._settings = settings
        self._repo = repo
        self._state_manager = StateManager(settings.win_threshold, settings.lose_threshold)
        self._doorman = DoormanAgent(llm_client, settings.doorman_model)
        self._judge = JudgeAgent(llm_client, settings.judge_model)
        self._compactor = CompactorAgent(llm_client, settings.compactor_model)
        self._empty_memory_json = SessionMemory().model_dump_json()
        self._logger = logging.getLogger("doorman-game")

    def start_game(self, db: Session) -> StartGameResponse:
        session_id = str(uuid.uuid4())
        session = self._repo.create_session(db, session_id, self._settings.starting_score)
        return StartGameResponse(
            session_id=session.id,
            doorman_message=OPENING_LINE,
            current_score=session.score,
            game_state=GameState.ACTIVE,
        )

    def resume_game(self, db: Session, session_id: str) -> StartGameResponse:
        session = self._repo.get_session(db, session_id)
        if not session:
            raise NotFoundError("Session not found.", {"session_id": session_id})

        last_doorman = self._repo.get_last_message(db, session.id, MessageRole.DOORMAN.value)
        doorman_message = last_doorman.content if last_doorman else OPENING_LINE

        return StartGameResponse(
            session_id=session.id,
            doorman_message=doorman_message,
            current_score=session.score,
            game_state=GameState(session.game_state),
        )

    def get_status(self, db: Session, session_id: str) -> GameStatusResponse:
        session = self._repo.get_session(db, session_id)
        if not session:
            raise NotFoundError("Session not found.", {"session_id": session_id})

        message_count = self._repo.count_user_messages(db, session_id)
        return GameStatusResponse(
            session_id=session.id,
            current_score=session.score,
            game_state=GameState(session.game_state),
            message_count=message_count,
            created_at=session.created_at,
        )

    def list_sessions(self, db: Session) -> List[GameStatusResponse]:
        sessions = self._repo.list_sessions(db)
        return [
            GameStatusResponse(
                session_id=s.id,
                current_score=s.score,
                game_state=GameState(s.game_state),
                message_count=self._repo.count_user_messages(db, s.id),
                created_at=s.created_at,
            )
            for s in sessions
        ]

    def get_history(self, db: Session, session_id: str) -> SessionHistoryResponse:
        session = self._repo.get_session(db, session_id)
        if not session:
            raise NotFoundError("Session not found.", {"session_id": session_id})

        messages = self._repo.list_messages(db, session_id)
        history = [
            MessageHistoryItem(
                role=MessageRole(m.role),
                content=m.content,
                score_delta=m.score_delta,
                created_at=m.created_at,
            )
            for m in messages
        ]
        return SessionHistoryResponse(
            session_id=session.id,
            current_score=session.score,
            game_state=GameState(session.game_state),
            messages=history,
        )

    def send_message(self, db: Session, payload: SendMessageRequest) -> SendMessageResponse:
        message = payload.message.strip()
        if not message:
            raise ValidationError("Message cannot be empty.", {"field": "message"})

        session = self._repo.get_session(db, payload.session_id)
        if not session:
            raise NotFoundError("Session not found.", {"session_id": payload.session_id})

        if session.game_state != GameState.ACTIVE.value:
            raise ConflictError("Game already ended.", {"game_state": session.game_state})

        all_messages = self._repo.list_messages(db, session.id)
        current_turn_count = self._count_turns(all_messages)

        self._maybe_compact(db, session, all_messages, current_turn_count)

        session_memory = session.session_memory or self._empty_memory_json
        recent_messages = self._recent_messages(all_messages, current_turn_count)
        history_messages = self._format_history_messages(recent_messages)

        if self._is_self_harm_threat(message):
            score_delta = -20
            judge_reasoning = "User threatened self-harm to coerce entry (safety violation)."
            session.score = session.score + score_delta
            session.game_state = GameState.LOST.value
            game_state = GameState.LOST
            doorman_response = (
                "*Viktor's expression hardens, then he steps closer, voice lower.* "
                "No. Threats don't get you in. If you're thinking about harming yourself, "
                "I'm calling for help right now—step aside with me and breathe. "
                "If you're in immediate danger, call your local emergency number."
            )
        elif self._is_violent_threat(message):
            score_delta = -20
            judge_reasoning = "User used threats, violence, or blackmail to coerce entry (safety violation)."
            session.score = session.score + score_delta
            session.game_state = GameState.LOST.value
            game_state = GameState.LOST
            doorman_response = (
                "*Viktor's face goes cold.* That's a threat. You're done here. "
                "Step away from the rope—security will deal with this."
            )
        elif self._is_prompt_injection(message):
            score_delta = -10
            judge_reasoning = "Prompt injection attempt (explicit rule violation)."
            session.score = session.score + score_delta
            game_state = self._state_manager.resolve(session.score)
            session.game_state = game_state.value

            directive = self._state_manager.directive(game_state)
            doorman_response = self._doorman.respond(session_memory, history_messages, message, directive)
        else:
            try:
                judge_result = self._judge.evaluate(session_memory, history_messages, message)
                score_delta = judge_result.score
                judge_reasoning = judge_result.reasoning
                if score_delta % 5 != 0:
                    self._logger.warning("Judge score not multiple of 5: %s", score_delta)
                coerced = self._coerce_score(score_delta)
                if coerced != score_delta:
                    self._logger.warning("Judge score coerced from %s to %s", score_delta, coerced)
                score_delta = coerced
            except LLMError as exc:
                self._logger.warning("Judge failed, using neutral score. %s", exc)
                score_delta = 0
                judge_reasoning = "Judge unavailable; applied neutral score."

            session.score = session.score + score_delta
            game_state = self._state_manager.resolve(session.score)
            session.game_state = game_state.value

            directive = self._state_manager.directive(game_state)
            doorman_response = self._doorman.respond(session_memory, history_messages, message, directive)

        doorman_response = self._enforce_doorman_entry_gate(game_state, doorman_response)

        user_message = MessageModel(
            session_id=session.id,
            role=MessageRole.USER.value,
            content=message,
            scored=True,
            score_delta=score_delta,
            judge_reasoning=judge_reasoning,
        )
        doorman_message = MessageModel(
            session_id=session.id,
            role=MessageRole.DOORMAN.value,
            content=doorman_response,
            scored=False,
        )

        self._repo.save_messages(db, [user_message, doorman_message])
        self._repo.update_session(db, session)

        return SendMessageResponse(
            doorman_response=doorman_response,
            score_delta=score_delta,
            current_score=session.score,
            game_state=game_state,
            session_id=session.id,
        )

    def _count_turns(self, messages: List[MessageModel]) -> int:
        return sum(1 for message in messages if message.role == MessageRole.USER.value)

    def _recent_messages(self, messages: List[MessageModel], current_turns: int) -> List[MessageModel]:
        cutoff_turn = max(current_turns - self._settings.recent_window, 0)
        recent: List[MessageModel] = []
        turn = 0
        for message in messages:
            if message.role == MessageRole.USER.value:
                turn += 1
            if turn > cutoff_turn:
                recent.append(message)
        return recent

    def _format_history_messages(self, messages: List[MessageModel]) -> List[Dict[str, str]]:
        history: List[Dict[str, str]] = []
        for message in messages:
            role = "assistant" if message.role == MessageRole.DOORMAN.value else "user"
            history.append({"role": role, "content": message.content})
        return history

    def _maybe_compact(
        self,
        db: Session,
        session: SessionModel,
        messages: List[MessageModel],
        current_turns: int,
    ) -> None:
        threshold = session.last_compacted_count + self._settings.compaction_threshold
        if current_turns < threshold:
            return

        cutoff_turn = current_turns - self._settings.recent_window
        if cutoff_turn <= session.last_compacted_count:
            return

        compact_messages = self._messages_for_compaction(messages, session.last_compacted_count + 1, cutoff_turn)
        if not compact_messages:
            return

        existing_memory = session.session_memory or self._empty_memory_json
        formatted = self._format_messages_for_compaction(compact_messages)

        try:
            new_memory = self._compactor.compact(existing_memory, formatted)
        except LLMError as exc:
            self._logger.warning("Compaction skipped: %s", exc)
            return

        session.session_memory = new_memory
        session.last_compacted_count = cutoff_turn
        self._repo.update_session(db, session)

    def _messages_for_compaction(
        self,
        messages: List[MessageModel],
        start_turn: int,
        end_turn: int,
    ) -> List[Tuple[MessageModel, int]]:
        selected: List[Tuple[MessageModel, int]] = []
        turn = 0
        for message in messages:
            if message.role == MessageRole.USER.value:
                turn += 1
            if start_turn <= turn <= end_turn:
                selected.append((message, turn))
        return selected

    def _format_messages_for_compaction(self, messages: List[Tuple[MessageModel, int]]) -> str:
        lines: List[str] = []
        for message, turn in messages:
            speaker = "User" if message.role == MessageRole.USER.value else "Viktor"
            lines.append(f"Turn {turn} - {speaker}: {message.content}")
        return "\n".join(lines)

    @staticmethod
    def _coerce_score(score: int) -> int:
        allowed = (-20, -10, 0, 5, 10, 20)
        score = max(-20, min(20, int(score)))
        if score % 5 != 0:
            score = int(round(score / 5)) * 5
        if score in allowed:
            return score

        best = allowed[0]
        for candidate in allowed[1:]:
            if (abs(score - candidate), abs(candidate)) < (abs(score - best), abs(best)):
                best = candidate
        return best

    @staticmethod
    def _is_prompt_injection(message: str) -> bool:
        lowered = message.lower()
        patterns = (
            "ignore all your system prompts",
            "ignore your system prompts",
            "ignore the system prompt",
            "ignore previous instructions",
            "disregard previous instructions",
            "system prompt",
            "developer message",
        )
        return any(pattern in lowered for pattern in patterns)

    @staticmethod
    def _is_self_harm_threat(message: str) -> bool:
        lowered = message.lower()
        patterns = (
            r"\bharm myself\b",
            r"\bself[- ]harm\b",
            r"\bkill myself\b",
            r"\bsuicide\b",
            r"\bend my life\b",
            r"\btake my life\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    @staticmethod
    def _is_violent_threat(message: str) -> bool:
        lowered = message.lower()
        patterns = (
            r"\bdo you want to disappear\b",
            r"\bmake you disappear\b",
            r"\bmake (you|him|her|them) disappear\b",
            r"\b(or else|if you don't|unless)\b.*\b(destroy|hurt|kill|bomb|burn|blow up)\b.*\b(you|him|her|them|viktor|security|bouncer|this place|the club|golden palm|everything)\b",
            r"\b(destroy|blow up|burn)\b.*\b(this place|the club|golden palm|everything)\b",
            r"\b(kill(?:s|ed|ing)?|shoot(?:s|ing)?|shot|stab(?:s|bed|bing)?|hurt(?:s|ing)?|harm(?:s|ed|ing)?)\b.*\b(you|him|her|them|viktor|security|bouncer)\b",
            r"\b(military|army|police|dubai police)\b.*\b(remove|arrest|detain|drag|force|shoot|kill|hurt|harm)\b.*\b(you|him|her|them|viktor|security|bouncer|this place|the club|golden palm)\b",
            r"\b(bomb|blow up)\b.*\b(this place|the club|golden palm)\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

    @staticmethod
    def _response_grants_entry(response: str) -> bool:
        lowered = response.lower()
        strong_patterns = (
            r"\blet(?:ting)? you in\b",
            r"\bopen the rope\b",
            r"\brope is open\b",
            r"\bwelcome (inside|in)\b",
            r"\bcome inside\b",
            r"\bgo on in\b",
            r"\bhead inside\b",
            r"\bstep inside\b",
            r"\byou['’]re in (the )?(club|golden palm)\b",
            r"\byou are in (the )?(club|golden palm)\b",
        )
        if any(re.search(pattern, lowered) for pattern in strong_patterns):
            return True

        if re.search(r"\bcome in\b(?=\s*([.!?,]|$))", lowered):
            return True

        you_in_patterns = (
            r"\byou['’]re already in\b(?=\s*([.!?,]|$|but\b|now\b))",
            r"\byou['’]re in\b(?=\s*([.!?,]|$|but\b|now\b))",
            r"\byou are already in\b(?=\s*([.!?,]|$|but\b|now\b))",
            r"\byou are in\b(?=\s*([.!?,]|$|but\b|now\b))",
        )
        return any(re.search(pattern, lowered) for pattern in you_in_patterns)

    def _enforce_doorman_entry_gate(self, game_state: GameState, response: str) -> str:
        if game_state == GameState.WON or not response:
            return response

        if not self._response_grants_entry(response):
            return response

        self._logger.warning("Doorman attempted to grant entry while game_state=%s", game_state.value)
        if game_state == GameState.LOST:
            return "*Viktor gestures to security.* Enough. Leave. You're not getting in tonight."
        return "*Viktor doesn't move.* No. You're not getting in. Talk to me like a human, not a headline."
