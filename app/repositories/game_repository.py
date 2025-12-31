from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from ..models.db_models import MessageModel, SessionModel
from ..schemas.game import GameState, MessageRole


class GameRepository:
    def create_session(self, db: Session, session_id: str, starting_score: int) -> SessionModel:
        session = SessionModel(
            id=session_id,
            score=starting_score,
            game_state=GameState.ACTIVE.value,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_session(self, db: Session, session_id: str) -> Optional[SessionModel]:
        return db.query(SessionModel).filter(SessionModel.id == session_id).first()

    def update_session(self, db: Session, session: SessionModel) -> SessionModel:
        session.updated_at = datetime.utcnow()
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def save_messages(self, db: Session, messages: List[MessageModel]) -> None:
        for message in messages:
            db.add(message)
        db.commit()

    def list_messages(self, db: Session, session_id: str) -> List[MessageModel]:
        return (
            db.query(MessageModel)
            .filter(MessageModel.session_id == session_id)
            .order_by(MessageModel.id.asc())
            .all()
        )

    def count_user_messages(self, db: Session, session_id: str) -> int:
        return (
            db.query(MessageModel)
            .filter(
                MessageModel.session_id == session_id,
                MessageModel.role == MessageRole.USER.value,
            )
            .count()
        )

    def get_last_message(
        self,
        db: Session,
        session_id: str,
        role: Optional[str] = None,
    ) -> Optional[MessageModel]:
        query = db.query(MessageModel).filter(MessageModel.session_id == session_id)
        if role:
            query = query.filter(MessageModel.role == role)
        return query.order_by(MessageModel.id.desc()).first()

    def list_sessions(self, db: Session) -> List[SessionModel]:
        return (
            db.query(SessionModel)
            .order_by(SessionModel.updated_at.desc())
            .all()
        )
