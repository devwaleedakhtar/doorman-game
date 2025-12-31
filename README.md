# game-spec

Conversational doorman game built with FastAPI + OpenAI SDK (Morpheus gateway).

## Quick start

Install deps:

```bash
python -m pip install -r requirements.txt
```

Create `.env` from the example:

```bash
copy .env.example .env
```

Edit `.env` and set at minimum:

- `LLM_API_KEY`
- `DOORMAN_MODEL`
- `JUDGE_MODEL`

Start the dev server:

```bash
python -m uvicorn app.main:app --reload --env-file .env
```

The SQLite database is created automatically on startup.

## Terminal UI (no manual API calls)

Start the API first, then run the CLI:

```bash
python -m uvicorn app.main:app --reload --env-file .env
```

```bash
python cli.py
```

Set `API_BASE_URL` in `.env` if the API is running on a different host/port.

## API endpoints

- `GET /health` -> `{"status":"ok"}`
- `GET /docs` -> Swagger UI
- `POST /game/start` -> returns `session_id` + opening line
- `POST /game/message` -> send user message
- `GET /game/status/{session_id}` -> returns current game state

Example:

```bash
curl -X POST http://127.0.0.1:8000/game/start
```

```bash
curl -X POST http://127.0.0.1:8000/game/message ^
  -H "Content-Type: application/json" ^
  -d "{\"session_id\":\"<uuid>\",\"message\":\"Let me in.\"}"
```

## Environment notes

- `LLM_BASE_URL` defaults to `https://api.mor.org/api/v1`.
- `DATABASE_URL` defaults to `sqlite:///./doorman.db`.

## View the SQLite DB

If you want to inspect the DB quickly via Python:

```bash
python -c "import sqlite3; conn=sqlite3.connect('doorman.db'); print(conn.execute('select * from sessions').fetchall())"
```
