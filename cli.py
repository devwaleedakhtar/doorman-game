from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict

import httpx
from dotenv import load_dotenv


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


SESSION_FILE = Path(__file__).resolve().with_name(".doorman_session")


def _load_session_id() -> str | None:
    try:
        session_id = SESSION_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return None
    return session_id or None


def _save_session_id(session_id: str) -> None:
    try:
        SESSION_FILE.write_text(f"{session_id}\n", encoding="utf-8")
    except OSError:
        pass


def _confirm(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer in {"y", "yes"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Doorman game CLI")
    parser.add_argument("--session-id", help="Resume a specific session ID.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the last session stored by this CLI.",
    )
    return parser.parse_args()


def _score_meter(score: int, lose: int, win: int, width: int = 24) -> str:
    if win <= lose:
        return ""
    ratio = (score - lose) / float(win - lose)
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _print_status(score: int, delta: int | None, state: str, lose: int, win: int) -> None:
    meter = _score_meter(score, lose, win)
    delta_text = "" if delta is None else f" ({delta:+})"
    print(f"Score: {score}{delta_text} | State: {state} {meter}")


def _safe_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    error = payload.get("error", {})
    code = error.get("code", "ERROR")
    message = error.get("message", "Request failed.")
    return f"[{code}] {message}"


def run_cli() -> int:
    load_dotenv()
    args = _parse_args()
    base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    win_threshold = _get_int("WIN_THRESHOLD", 100)
    lose_threshold = _get_int("LOSE_THRESHOLD", -50)
    timeout_seconds = _get_int("CLI_TIMEOUT_SECONDS", 120)

    session_id = args.session_id
    if not session_id and args.resume:
        session_id = _load_session_id()
        if not session_id:
            print("No saved session to resume.")

    print("Doorman Game (type 'exit' to quit)")
    print(f"API: {base_url}")
    print("-" * 40)

    try:
        with httpx.Client(base_url=base_url, timeout=float(timeout_seconds)) as client:
            start_payload: Dict[str, Any]
            if session_id:
                resume = client.post("/game/resume", json={"session_id": session_id})
                if resume.status_code >= 400:
                    print(_safe_error(resume))
                    if not _confirm("Start a new game instead?"):
                        return 1
                    session_id = None
                else:
                    start_payload = resume.json()
                    session_id = start_payload["session_id"]
            if not session_id:
                start = client.post("/game/start")
                if start.status_code >= 400:
                    print(_safe_error(start))
                    return 1
                start_payload = start.json()
                session_id = start_payload["session_id"]

            _save_session_id(session_id)
            print(f"Viktor: {start_payload['doorman_message']}")
            _print_status(
                start_payload["current_score"],
                None,
                start_payload["game_state"],
                lose_threshold,
                win_threshold,
            )

            if start_payload["game_state"] != "active":
                print("Game ended.")
                return 0

            while True:
                try:
                    user_message = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting.")
                    return 0

                if not user_message:
                    continue
                if user_message.lower() in {"exit", "quit"}:
                    return 0

                response = client.post(
                    "/game/message",
                    json={"session_id": session_id, "message": user_message},
                )
                if response.status_code >= 400:
                    print(_safe_error(response))
                    continue

                payload: Dict[str, Any] = response.json()
                print(f"Viktor: {payload['doorman_response']}")
                _print_status(
                    payload["current_score"],
                    payload["score_delta"],
                    payload["game_state"],
                    lose_threshold,
                    win_threshold,
                )

                if payload["game_state"] != "active":
                    print("Game ended.")
                    return 0
    except httpx.RequestError as exc:
        print(f"Connection error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run_cli())
