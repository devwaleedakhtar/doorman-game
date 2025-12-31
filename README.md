# game-spec

## Run the API (FastAPI)

Install deps:

```bash
python -m pip install -r requirements.txt
```

Start the dev server:

```bash
python -m uvicorn app.main:app --reload --env-file .env
```

Endpoints:

- `GET /health` -> `{"status":"ok"}`
- `GET /docs` -> Swagger UI
