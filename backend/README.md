# OpenCall backend

FastAPI HTTP backend with LiveKit Agents speech providers. Use Python 3.11–3.13 (tested with 3.13); Silero does not currently install on this machine’s Python 3.14.

## Local setup

Run from the repository root:

```bash
cd backend
python3.13 -m venv .venv-voice
source .venv-voice/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

For the Vercel HTTP API, `requirements.txt` contains only HTTP runtime dependencies.
The local development requirements also install the LiveKit voice worker dependencies;
`voiceagent/requirements.txt` installs them for the worker deployment.

Use a dedicated virtual environment for this backend. If an older `.venv` also
contains Google ADK or LiteLLM, those unrelated packages can conflict with
LiveKit 1.8.9 dependencies; a fresh environment avoids that conflict.
Environment variables override
values in `backend/.env`; the app also works with the defaults without this file.

## Endpoints

- `GET /api/v1/auth/me` — returns the logged-in user, or `401`.
- `POST /api/v1/conversation/connect` — issues room connection details (login required).
- `GET /api/v1/conversation/phonebook` — the signed-in user's username and description.
- `PUT /api/v1/conversation/phonebook` — updates the signed-in user's description.
- `GET /api/v1/conversation/tasks` — returns the signed-in user's saved call requests.
- `GET /` — app name and documentation URL.
- `GET /api/v1/health` — returns `{"status":"ok"}` for process health.
- `POST /api/v1/speech/transcribe` — transcribes a WAV recording through Gnani.
- `POST /api/v1/speech/synthesize` — reads transcript text with Gnani TTS and returns WAV audio.
- `GET /api/v1/speech/voices?language_code=en-IN` — available playback voices and the default for a language.
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
The health endpoint checks only that the app responds.

## Authentication and database

Users sign in with Google through Firebase. The frontend creates an HttpOnly
Firebase session cookie, which the backend verifies before syncing the user's
identity to the Supabase Postgres `opencall.users` table. Set `DATABASE_URL`
and Firebase service-account configuration in `backend/.env`; see `.env.example`.
Apply `backend/migrations/001_users.sql`, `002_farming_tasks.sql`, and
`003_crop_knowledge.sql` to the target database, followed by
`006_optional_crop_embeddings.sql` before seeding new crop records. Seed the crop
guidance with `PYTHONPATH=.:backend backend/.venv-voice/bin/python -m tools.ingest_crop_knowledge`.
The worker searches reviewed crop records using Postgres text search; it does not
load an embedding model. Reviewed records and sources are in
`backend/data/crop_knowledge_seed.json`.
The API and voice worker must connect to the same database. A user without a
phone number receives a generated identifier; phonebook descriptions are stored
on the user row. See [Phonebook](phonebook.md) for the API and update behavior.

## LiveKit speech backend

Speech runs through `livekit-plugins-gnani==1.8.9` and LiveKit Agents 1.8.9.
The standalone transcription endpoint converts the
validated WAV into a LiveKit `rtc.AudioFrame` and awaits `STT.recognize()`.
Playback collects a LiveKit `tts.ChunkedStream` into an audio frame and returns WAV.
Both endpoints are asynchronous; each request owns and closes its provider and
`aiohttp` session, including on failures or cancellation. Clients are never shared
between requests, so language and voice settings cannot leak across calls.

Set `GNANI_API_KEY` in `backend/.env`, then install `requirements.txt`.
The key stays on the backend. Providers are created on demand, so health checks
and startup work without a key. Restart the server after changing configuration.

`app/services/gnani.py` adapts the HTTP routes to LiveKit audio types.
`app/services/livekit_gnani.py` subclasses the Gnani plugin to own HTTP sessions
outside a LiveKit worker job. It also provides a small Timbre v3 REST
`ChunkedStream`: the published plugin only forwards `language` for v2.5, while
v3 requires it. This adapter explicitly sends `model="timbre-v3.0"`, selected
voice, language, and delivery-tagged text through LiveKit's audio emitter.
Output is mono 16-bit WAV at **44.1 kHz**, the highest rate accepted by this
plugin release (previously 48 kHz). Input remains mono 16-bit WAV at 16 kHz.
Requests use a 60-second provider timeout and no automatic retries.

The recording endpoints use LiveKit speech classes inside FastAPI. The `/try`
page uses the continuous conversation worker described below.

References: [Gnani LiveKit plugin](https://docs.gnani.ai/livekit/introduction),
[Gnani TTS REST contract](https://docs.gnani.ai/api/TTS/tts-inference).

## Speech-to-text API

Send a multipart request to `POST /api/v1/speech/transcribe`. This produces text in the spoken language;
it does not translate between languages. The backend keeps the API key private. Both speech POST endpoints require a signed-in `firebase_session` cookie and share a limit of 20 requests per user per minute per API process. Deployments with multiple processes or serverless replicas need a shared gateway or distributed limiter for a global limit.

The request has two fields: `audio` (a mono, 16-bit PCM WAV file at 16 kHz) and
`language_code` (defaults to `en-IN`). Supported language codes are `en-IN`,
`hi-IN`, `te-IN`, `ta-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `gu-IN`, `bn-IN`, and `pa-IN`.
The backend rejects empty, malformed, incomplete, oversized (over 8 MB), and
overlong (over 60 seconds) recordings before calling Gnani.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/speech/transcribe \
  --cookie "firebase_session=<session-cookie>" \
  -F "audio=@recording.wav;type=audio/wav" \
  -F "language_code=en-IN"
```

Example response:

```json
{"transcript":"Hello world","language_code":"en-IN","request_id":"request-uuid"}
```

Invalid input returns `422`, oversized input returns `413`, missing plugin or key
returns `503`, and upstream transcription failures return `502` with a safe
message. The app does not save audio or transcript files. The recording is sent
to Gnani for processing. The health endpoint does not verify Gnani connectivity.

Run backend tests from `backend/`:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Endpoint tests mock the speech boundary; transport tests exercise the installed
LiveKit providers with mocked HTTP responses. Live transcription and playback
still require a working key, network access, and browser verification.

## Transcript playback

The transcript panel's **Listen** button posts JSON to `/api/v1/speech/synthesize`:

```bash
curl http://127.0.0.1:8000/api/v1/speech/synthesize \
  --cookie "firebase_session=<session-cookie>" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Hello. Welcome to OpenCall.","language_code":"en-IN","voice":"Shivani","delivery":"excited"}' \
  --output speech.wav
```

The endpoint accepts 1–5,000 characters after trimming whitespace and uses
`timbre-v3.0` with WAV output. `voice` is optional and defaults to `Shivani`.
All 13 v3 voices speak every supported language: Shivani, Avinash, Lakshmi,
Kalpana, Chetana, Vasudha, Riyaa, Tarika, Shubham, Prakash, Devansh, Yashraj,
and Harshad. Unknown voices and voices from earlier models return `422` before
Gnani is called. The catalog follows the
[Gnani voice documentation](https://docs.gnani.ai/api/TTS/available-voices).

The optional `delivery` defaults to `neutral`. Supported values are `excited`,
`whispers`, `shouting`, `laugh`, `giggle`, `sigh`, `exhales`, `sniffles`, `yawns`,
`coughs`, `clears throat`, `slow`, and `pauses`. The backend prepends the matching
inline tag for synthesis without changing the transcript displayed in the UI.
For example, `excited` sends `<excited> Hello world` to Gnani. These are documented
v3 delivery cues; arbitrary emotions such as `sad` are not accepted.
See [Gnani audio tags](https://docs.gnani.ai/api/TTS/tts-audio-tags).

The response is `audio/wav` with `Cache-Control: no-store` and an
`X-API-Request-ID` header. Request IDs identify the OpenCall HTTP request;
the plugin manages provider-side IDs separately. The key remains on the backend. Invalid text, voice,
language, or delivery returns `422`; missing configuration returns `503`;
provider failures return `502`.

Choose **Voice** and **Delivery** beside **Listen**. Changing either stops
playback and discards the previous audio. Clicking **Listen** generates audio
with the new settings. **Stop** stops playback; **Play** reuses that audio.
If the browser blocks automatic playback after generation, click **Play**.
Beginning a new recording or navigating away stops playback and releases audio
resources. The frontend continues to use Tailwind for these controls.


## Migration validation

The migration passes 27 backend tests, including the installed LiveKit plugin's
STT events, TTS decoding, WAV output, concurrent request isolation, cancellation,
and HTTP session cleanup, with provider HTTP responses mocked. OpenCall's runtime
dependency chain was checked independently of unrelated packages in the existing
virtual environment. Live Gnani requests and browser audio remain unverified.


## Continuous voice conversations

The `/try` page supports a room-based, continuous conversation:

```text
Browser microphone → LiveKit room → Gnani streaming STT
                                     ↓
                                Groq streaming LLM
                                     ↓
Browser speakers   ← LiveKit room ← Timbre v3 WebSocket TTS
```

Start once and speak naturally. Silero detects speech and pauses; LiveKit commits
turns automatically, manages conversation context, and interrupts outgoing audio
when you speak over the assistant. The initial settings use 350 ms of speech for
an interruption and a 500 ms minimum endpointing delay. False interruptions can
resume playback. This is VAD-based turn detection; background noise and short
pauses can require tuning. Echo cancellation and noise suppression are enabled in
the browser. Headphones help avoid the assistant hearing its own output.

The LLM streams text; LiveKit's sentence adapter sends sentences to the Gnani
WebSocket endpoint as they become available. Gnani streams raw mono PCM audio
at 24 kHz, emitted to the room in 20 ms frames. The full reply is never collected
into a WAV before playback. Timbre v3 voice and language are passed explicitly.
Cancellation closes the active TTS socket and LiveKit stops the queued playback.
The agent's conversation history is managed by LiveKit, including interrupted turns.

### Run locally

Agent tools, including current/forecast/historical weather, are documented in
[tools/](tools/README.md).

After installing backend requirements, frontend dependencies (`cd frontend && bun install`),
and LiveKit (`brew install livekit`), start everything from one terminal:

```bash
# From the repository root (also works from frontend/):
bun run dev
```

This starts LiveKit, the Python 3.13 voice worker,
FastAPI, and Next.js in order.
It waits for readiness, restarts managed processes if they exit, and reuses
services already running. Keep this terminal open; Ctrl+C stops the processes
it started. Processes started separately remain under their original terminal.
The worker health endpoint uses local port `8081` (`VOICE_WORKER_PORT` can override it).
Use the default local LiveKit URL/key/secret from `.env.example` for automatic server startup.
Provider keys must be configured in `backend/.env`.

The connect API now checks LiveKit and the local worker before returning join
details. An unavailable service returns `503`, instead of a valid-looking token
followed by a browser connection failure. Starting FastAPI alone does not start
the voice services. To run each process manually, use the commands below.

Install [LiveKit server](https://docs.livekit.io/home/self-hosting/local/) on macOS:

```bash
brew install livekit
livekit-server --dev --bind 127.0.0.1
```

In a second terminal, install backend requirements in the Python 3.13 environment
above. Keep the existing `GNANI_API_KEY` and `GROQ_API_KEY` in `backend/.env`.
The local server defaults match `.env.example`: `ws://127.0.0.1:7880`, key
`devkey`, secret `secret`. Then run FastAPI:

```bash
cd backend
source .venv-voice/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In a third terminal, run the agent worker:

```bash
cd backend
source .venv-voice/bin/activate
python -m app.voice_agent dev
```

In a fourth terminal, start the frontend:

```bash
cd frontend
bun install
bun run dev:frontend
```

Open `http://localhost:3000`, sign in, choose a language and voice on `/try`, and click
**Start conversation**. Allow the microphone. The agent greets you and then
listens continuously. Use **Mute microphone**, **End conversation**, or
**Enable audio** if browser autoplay is blocked. Settings are locked during a
session. Transcripts are shown in this tab and cleared when the session ends.
The worker reads the signed-in username’s saved phonebook description when a
conversation starts. On session shutdown, useful details from the user’s speech
are merged into that description. Only the description is saved; conversation
transcripts, call records, and separate summaries are not stored. The phonebook
API also supports explicit edits.
A connection failure, permission denial, missing worker, or lost connection is
shown in the UI. Leaving the page disconnects and releases the microphone.
Sessions end after `CONVERSATION_MAX_SECONDS` (default 3 minutes). Thirty seconds
before the end the agent warns the caller, and at the limit it says goodbye before
hanging up.

When something fails, the call degrades gently instead of dropping:

- If `GROQ_MODEL` errors or takes over 5 s, the reply comes from
  `GROQ_FALLBACK_MODEL` (default `openai/gpt-oss-120b`; empty disables it).
- If both models fail, the agent asks the caller to repeat. After two failed
  replies in a row it apologises and ends the call.
- If speech recognition fails, the agent apologises and ends the call. If speech
  output fails, only the screen explains.
- The agent sends the end reason on the `call_status` data topic, and `/try`
  shows a matching message with a "Call again" button.
- The fixed lines are in `app/services/call_messages.py`; have native speakers
  review them.

### Configuration and connection contract

`POST /api/v1/conversation/connect` requires the login cookie and accepts
`{"language_code":"en-IN","voice":"Shivani"}`. It returns `server_url`,
`participant_token`, `room_name`, and `participant_identity` with `no-store`.
Each call creates a unique room identity and signs a 10-minute join token,
restricted to that room and microphone publication. The token embeds explicit
worker dispatch to `opencall-conversation` with the validated voice/language and
the authenticated username. The worker reads that username’s description from
Supabase Postgres. The browser calls the
same-origin `/api/conversation/connect` proxy to forward its session cookie.
LiveKit dispatches the worker when the participant joins. Provider keys and the
LiveKit API secret never reach the browser. Token expiry limits joining; the
worker's duration limit ends an already connected conversation.

`GROQ_MODEL` defaults to `openai/gpt-oss-20b`. Override it with another Groq
chat model available to your account. A real LiveKit Cloud deployment can use
`LIVEKIT_URL=wss://...`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` from that
project, with the backend and worker configured identically. The local development
key/secret are only for the loopback server. Conversation tokens require a verified Firebase session.

Continuous conversation requires all four processes (room server, API, worker,
frontend). A passing health endpoint or issued token does not prove a worker has
joined or that provider audio works. Browser microphone and interruption behavior
must be verified with a real conversation.


### Continuous conversation validation

- 33 backend tests pass in the clean Python 3.13 environment; `pip check` passes.
- Frontend ESLint and TypeScript checks pass.
- The real `/conversation/connect` endpoint returns 200 and valid connection details.
- A live synthetic-audio test connected to local LiveKit 1.13.10, dispatched the
  worker, received Gnani/Groq replies over room audio, and published speech during
  an assistant reply. Agent state changed from speaking to listening, then back to
  thinking and speaking for the new turn. This verifies the pipeline and
  interruption handling with generated speech; actual browser microphone,
  autoplay, speaker echo, and perceived conversation quality still need testing.
- `bun run build` was attempted but Turbopack's Tailwind loader failed to bind a
  local port with `Operation not permitted`. Production build verification remains
  incomplete. No browser automation surface was available for visual verification.

The original 27-test migration validation above applies to the recording endpoints;
these newer checks cover the room-based conversation implementation.

### Groq model usage

The live conversation uses `GROQ_MODEL` (default `openai/gpt-oss-20b`).
Phonebook updates use the independent `GROQ_SUMMARY_MODEL` (default
`qwen/qwen3.8-27b`, with reasoning disabled). Set the summary model to a model
available to the same Groq account. There is no automatic fallback to the voice
model: if summarization fails or is truncated, the existing description is kept.
Phonebook summary requests preserve the first and last 6,000 characters of long
sessions and cap output at 512 tokens; details in the middle can be omitted.

Worker logs report provider-reported prompt, completion, total, cached and
reasoning token counts separately for `task=voice` and `task=phonebook_summary`.
These logs contain no transcript text. Missing or zero usage fields depend on the
provider. Model quotas and cached-token treatment depend on the Groq account.
A bilingual call without a saved description uses a fixed Hindi greeting; calls
with a saved description retain a personalized, model-generated greeting.
