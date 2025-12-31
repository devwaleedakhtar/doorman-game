from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


@dataclass(frozen=True)
class Settings:
    app_name: str
    llm_api_key: str
    llm_base_url: str
    llm_timeout_seconds: float
    llm_json_retries: int
    doorman_model: str
    judge_model: str
    compactor_model: str
    starting_score: int
    win_threshold: int
    lose_threshold: int
    compaction_threshold: int
    recent_window: int
    database_url: str
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_name = os.getenv("APP_NAME", "game-spec-api")
    llm_api_key = os.getenv("LLM_API_KEY", "").strip()
    if not llm_api_key:
        raise ValueError("LLM_API_KEY is required.")

    llm_base_url = os.getenv("LLM_BASE_URL", "https://api.mor.org/api/v1")
    llm_timeout_seconds = _get_float("LLM_TIMEOUT_SECONDS", 45.0)
    llm_json_retries = _get_int("LLM_JSON_RETRIES", 1)

    doorman_model = os.getenv("DOORMAN_MODEL", "").strip()
    judge_model = os.getenv("JUDGE_MODEL", "").strip()
    if not doorman_model or not judge_model:
        raise ValueError("DOORMAN_MODEL and JUDGE_MODEL are required.")

    compactor_model = os.getenv("COMPACTOR_MODEL", doorman_model).strip() or doorman_model

    return Settings(
        app_name=app_name,
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_timeout_seconds=llm_timeout_seconds,
        llm_json_retries=llm_json_retries,
        doorman_model=doorman_model,
        judge_model=judge_model,
        compactor_model=compactor_model,
        starting_score=_get_int("STARTING_SCORE", 30),
        win_threshold=_get_int("WIN_THRESHOLD", 100),
        lose_threshold=_get_int("LOSE_THRESHOLD", -50),
        compaction_threshold=_get_int("COMPACTION_THRESHOLD", 10),
        recent_window=_get_int("RECENT_WINDOW", 8),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./doorman.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
