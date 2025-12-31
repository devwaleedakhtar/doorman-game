from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    status_code = 500
    code = "APP_ERROR"

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)


class ValidationError(AppError):
    status_code = 400
    code = "VALIDATION_ERROR"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class LLMError(AppError):
    status_code = 502
    code = "LLM_ERROR"