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

## Architecture Decisions

The game was intentionally kept lean and simple, and added complexity was avoided. Still, the design phase consisted of carefully analyzing edge-cases (context limitations, scoring, prompts).

### Why No RAG?

RAG was not used at this stage, but can definitely be added as an improvement. Instead, we rely on **Rolling Memory + Recent Messages**:

- An up-to-date memory summary is maintained, extracting key claims, facts, and conflicts
- This summary is sent along with the last few turns of conversation
- Similar approach to ChatGPT's memory feature (they don't use RAG either)

### Database Choice

SQLite was chosen for simplicity. For production scalability, switch to PostgreSQL or equivalent.

### Dual-Agent Architecture

- **Doorman Agent** (smaller model): Handles persona and dialogue generation
- **Judge Agent** (larger model): Evaluates persuasiveness and assigns scores
- **Compactor Agent**: Summarizes conversation history when context grows too long

## Tradeoffs & Future Improvements

| Area | Current State | Future Improvement |
|------|---------------|-------------------|
| **UI** | Simple HTML/CSS/JS | Next.js for better DX and features |
| **Context Management** | Rolling Memory only | Rolling Memory + RAG for more robust context (especially useful for the smaller judge agent) |
| **Performance** | Sequential processing | Parallel processes, concurrent analysis, memory/context optimization |
| **Database** | SQLite | PostgreSQL for scalability |
