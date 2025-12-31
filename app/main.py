from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def create_app() -> FastAPI:
    """
    Create the FastAPI app instance.

    Keep this minimal; add routers/services as the project grows.
    """
    app = FastAPI(title=os.getenv("APP_NAME", "game-spec-api"))

    @app.get("/health", tags=["system"])
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse({"name": app.title, "docs": "/docs"})

    return app


app = create_app()


