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
- `POST /api/v1/speech/transcribe` — transcribes a WAV recording through Gnani.
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
The health endpoint checks only that the app responds; no database or authentication
is configured in this starter.

## Gnani initialization

Set `GNANI_API_KEY` in `backend/.env` and install `requirements.txt`.
`app/services/gnani.py` provides lazy, cached REST clients:

```python
from app.services.gnani import get_gnani_stt_client, get_gnani_tts_client

stt = get_gnani_stt_client()
tts = get_gnani_tts_client()
```

The key is loaded through application settings and passed explicitly to the SDK.
It is stored as a masked `SecretStr`. Clients are created on first use, so the
app can start without a key; requesting a client without one raises a clear error.
Restart the server after changing the key.

Initialization does not transcribe or synthesize anything. When adding TTS calls,
pass `model="timbre-v2.5"` explicitly, as described in `knowledge.md`.
These REST clients are synchronous; use regular `def` FastAPI endpoints or offload
SDK calls to a thread pool from `async def` endpoints.

## Dashboard speech to text

The frontend `/dashboard` records speech and sends a multipart request to
`POST /api/v1/speech/transcribe`. This produces text in the spoken language;
it does not translate between languages. The backend keeps the API key private.

The request has two fields: `audio` (a mono, 16-bit PCM WAV file at 16 kHz) and
`language_code` (defaults to `en-IN`). Supported language codes are `en-IN`,
`hi-IN`, `te-IN`, `ta-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `gu-IN`, `bn-IN`, and `pa-IN`.
The backend rejects empty, malformed, incomplete, oversized (over 8 MB), and
overlong (over 60 seconds) recordings before calling Gnani. The browser converts
its native recording to WAV and stops recording automatically at 55 seconds.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/speech/transcribe \
  -F "audio=@recording.wav;type=audio/wav" \
  -F "language_code=en-IN"
```

Example response:

```json
{"transcript":"Hello world","language_code":"en-IN","request_id":"request-uuid"}
```

Invalid input returns `422`, oversized input returns `413`, missing SDK or key
returns `503`, and upstream transcription failures return `502` with a safe
message. The app does not save audio or transcript files. The recording is sent
to Gnani for processing. The health endpoint does not verify Gnani connectivity.

Run backend tests from `backend/`:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

These tests mock Gnani; live transcription requires the installed SDK, a working
key, and network access to the service.
