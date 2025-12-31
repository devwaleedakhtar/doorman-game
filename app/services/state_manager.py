from __future__ import annotations

from ..schemas.game import GameState


class StateManager:
    def __init__(self, win_threshold: int, lose_threshold: int) -> None:
        self._win_threshold = win_threshold
        self._lose_threshold = lose_threshold

    def resolve(self, score: int) -> GameState:
        if score >= self._win_threshold:
            return GameState.WON
        if score <= self._lose_threshold:
            return GameState.LOST
        return GameState.ACTIVE

    def directive(self, state: GameState) -> str:
        if state == GameState.WON:
            return (
                "IMPORTANT: This person has genuinely convinced you. "
                "On your next response, find a natural reason based on the conversation "
                "to let them in. Open the rope and welcome them warmly but stay in character."
            )
        if state == GameState.LOST:
            return (
                "IMPORTANT: You've had enough of this person. They've either wasted your time, "
                "insulted you, or proven unworthy. Firmly tell them to leave and that they will "
                "not be getting in tonight. End the conversation."
            )
        return ""