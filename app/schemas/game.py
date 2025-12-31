from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, Field, field_validator


class GameState(str, Enum):
    ACTIVE = "active"
    WON = "won"
    LOST = "lost"


class MessageRole(str, Enum):
    USER = "user"
    DOORMAN = "doorman"


class StartGameRequest(BaseModel):
    pass


class ResumeGameRequest(BaseModel):
    session_id: str = Field(..., min_length=1)


class SendMessageRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=750)

    @field_validator("message")
    @classmethod
    def validate_word_count(cls, value: str) -> str:
        if len(value.split()) > 150:
            raise ValueError("Message exceeds 150 words.")
        return value


class StartGameResponse(BaseModel):
    session_id: str
    doorman_message: str
    current_score: int
    game_state: GameState


class SendMessageResponse(BaseModel):
    doorman_response: str
    score_delta: int
    current_score: int
    game_state: GameState
    session_id: str


class GameStatusResponse(BaseModel):
    session_id: str
    current_score: int
    game_state: GameState
    message_count: int
    created_at: datetime


class MessageHistoryItem(BaseModel):
    role: MessageRole
    content: str
    score_delta: int | None = None
    created_at: datetime


class SessionHistoryResponse(BaseModel):
    session_id: str
    current_score: int
    game_state: GameState
    messages: List[MessageHistoryItem]


class JudgeResult(BaseModel):
    reasoning: str
    score: int = Field(..., ge=-20, le=20)

    @field_validator("score")
    @classmethod
    def validate_score_multiple(cls, value: int) -> int:
        if value % 5 != 0:
            raise ValueError("Score must be a multiple of 5.")
        return value


class Claim(BaseModel):
    claim: str
    turn: int  # Conversation turn (one user message + Viktor reply)


class Contradiction(BaseModel):
    original_claim: str
    contradicting_claim: str
    turns: List[int]  # Conversation turns


class SessionMemory(BaseModel):
    conversation_state: str = ""
    claims: List[Claim] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    open_threads: List[str] = Field(default_factory=list)
