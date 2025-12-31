from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config.settings import get_settings
from .models.database import get_db, init_db
from .utilities.errors import AppError
from .utilities.logging import setup_logging
from .schemas.game import (
    GameStatusResponse,
    ResumeGameRequest,
    SendMessageRequest,
    SendMessageResponse,
    SessionHistoryResponse,
    StartGameResponse,
)
from .repositories.game_repository import GameRepository
from .services.game_service import GameService
from .services.llm_client import get_llm_client

STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    logger = logging.getLogger("doorman-game")

    app = FastAPI(title=settings.app_name)

    @app.on_event("startup")
    def startup() -> None:
        init_db()

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logger.error("AppError %s: %s | details=%s", exc.code, exc.message, exc.details)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"] if part != "body"),
                "reason": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input provided",
                    "details": details,
                }
            },
        )

    def get_game_service() -> GameService:
        repo = GameRepository()
        llm_client = get_llm_client()
        return GameService(settings, repo, llm_client)

    @app.get("/health", tags=["system"])
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse({"name": app.title, "docs": "/docs"})

    @app.post("/game/start", response_model=StartGameResponse)
    def start_game(
        service: GameService = Depends(get_game_service),
        db=Depends(get_db),
    ) -> StartGameResponse:
        return service.start_game(db)

    @app.post("/game/resume", response_model=StartGameResponse)
    def resume_game(
        payload: ResumeGameRequest,
        service: GameService = Depends(get_game_service),
        db=Depends(get_db),
    ) -> StartGameResponse:
        return service.resume_game(db, payload.session_id)

    @app.post("/game/message", response_model=SendMessageResponse)
    def send_message(
        payload: SendMessageRequest,
        service: GameService = Depends(get_game_service),
        db=Depends(get_db),
    ) -> SendMessageResponse:
        return service.send_message(db, payload)

    @app.get("/game/status/{session_id}", response_model=GameStatusResponse)
    def game_status(
        session_id: str,
        service: GameService = Depends(get_game_service),
        db=Depends(get_db),
    ) -> GameStatusResponse:
        return service.get_status(db, session_id)

    @app.get("/game/sessions", response_model=List[GameStatusResponse])
    def list_sessions(
        service: GameService = Depends(get_game_service),
        db=Depends(get_db),
    ) -> List[GameStatusResponse]:
        return service.list_sessions(db)

    @app.get("/game/history/{session_id}", response_model=SessionHistoryResponse)
    def get_history(
        session_id: str,
        service: GameService = Depends(get_game_service),
        db=Depends(get_db),
    ) -> SessionHistoryResponse:
        return service.get_history(db, session_id)

    # Serve static files
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/play", include_in_schema=False)
    async def play() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
