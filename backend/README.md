# OpenCall backend

Minimal FastAPI backend. Requires Python 3.10 or newer.

## Local setup

Run from the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If `.venv` already exists, skip creating it. Environment variables override
values in `backend/.env`; the app also works with the defaults without this file.

## Endpoints

- `GET /` — app name and documentation URL.
- `GET /api/v1/health` — returns `{"status":"ok"}` for process health.
- `/docs` — interactive Swagger documentation.
- `/redoc` — ReDoc documentation.
- `/openapi.json` — OpenAPI schema.

Check the running server:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Structure

```text
app/
  main.py              # App factory, middleware, and root endpoint
  core/config.py       # Environment-backed settings
  api/router.py        # Routes mounted at /api/v1
  api/routes/health.py # Health endpoint and response schema
```

Add endpoint modules in `app/api/routes/` and include their routers in
`app/api/router.py`. Set `CORS_ORIGINS` to a JSON array in `.env` when the frontend
origin changes. The defaults allow the local Next.js frontend on port 3000.

For production, configure the actual frontend origins and run without `--reload`.
The health endpoint checks only that the app responds; no database, authentication,
or external services are configured in this starter.
