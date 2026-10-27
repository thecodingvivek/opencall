# OpenCall backend

FastAPI HTTP backend with LiveKit Agents speech providers. Use Python 3.11–3.13 (tested with 3.13); Silero does not currently install on this machine’s Python 3.14.

## Local setup

Run from the repository root:

```bash
cd backend
python3.13 -m venv .venv-voice
source .venv-voice/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Use a dedicated virtual environment for this backend. If an older `.venv` also
contains Google ADK or LiteLLM, those unrelated packages can conflict with
LiveKit 1.8.8 dependencies; a fresh environment avoids that conflict.
Environment variables override
values in `backend/.env`; the app also works with the defaults without this file.

## Endpoints

- `POST /api/v1/auth/login` — validates the local account and sets a session cookie.
- `GET /api/v1/auth/me` — returns the logged-in user, or `401`.
- `POST /api/v1/auth/logout` — revokes the session and clears its cookie.
- `POST /api/v1/conversation/connect` — issues room connection details (login required).
- `GET /api/v1/conversation/phonebook` — the signed-in user's username and description.
- `PUT /api/v1/conversation/phonebook` — updates the signed-in user's description.
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

## Local TinyDB login

Start the API and frontend (`cd frontend` then `bun run dev`) and open
`http://localhost:3000`. The dashboard redirects to `/login` without a valid
session. Log in with **username `demo`** and **password `opencall123`**.
Both dashboard pages share the session check and a **Log out** button.

API startup creates `backend/data/opencall.json` and seeds the demo account
only if it does not exist. TinyDB uses `users`, `sessions`, and `phonebook` tables. Passwords
use salted PBKDF2-SHA256 hashes; only SHA256 hashes of random session tokens
are stored. Sessions expire after 24 hours and survive an API restart.
The database directory is ignored by Git. Override its location with `TINYDB_PATH`
in `backend/.env`. To reset local data, stop the API and delete this file;
the next startup recreates the demo account and invalidates previous sessions.

The frontend proxies login/logout through `/api/auth/…`, so the browser receives
an HttpOnly, SameSite=Lax cookie on the frontend host. The server checks this
cookie against `/api/v1/auth/me` before rendering the dashboard. `API_URL` can
override the frontend server's backend address; it falls back to
`NEXT_PUBLIC_API_URL`, then `http://127.0.0.1:8000`.

Conversation endpoints require a valid session. The recording speech API routes
still accept requests without a session. The demo credentials are public,
cookies permit local HTTP, and there is no login rate limit.

The API and voice worker share TinyDB through `app/core/database.py`. Transactions
use a process lock plus a filesystem lock and atomically replace the JSON file
after all table updates. Run them on the **same machine and local filesystem**,
using the same absolute `TINYDB_PATH`; other tools must use this wrapper too.
Direct concurrent TinyDB access is unsafe, as described in
[TinyDB's storage guidance](https://tinydb.readthedocs.io/en/latest/usage.html#remarks-on-storage).

See [Phonebook](phonebook.md) for the username/description schema and API examples.

## LiveKit speech backend

Speech runs through `livekit-plugins-gnani==1.8.8` and LiveKit Agents 1.8.8.
The Next.js dashboard keeps the same HTTP endpoints. Transcription converts the
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

The recording endpoints use LiveKit speech classes inside FastAPI. The default
`/dashboard` now connects to the continuous conversation worker described below;
the recording studio remains at `/dashboard/transcribe`.

References: [Gnani LiveKit plugin](https://docs.gnani.ai/livekit/introduction),
[Gnani TTS REST contract](https://docs.gnani.ai/api/TTS/tts-inference).

## Dashboard speech to text

The frontend `/dashboard/transcribe` records speech and sends a multipart request to
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

The dashboard now supports a room-based, continuous conversation:

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
bun run dev
```

Open `http://localhost:3000/dashboard`, log in, choose a language and voice, and click
**Start conversation**. Allow the microphone. The agent greets you and then
listens continuously. Use **Mute microphone**, **End conversation**, or
**Enable audio** if browser autoplay is blocked. Settings are locked during a
session. Transcripts are shown in this tab and cleared when the session ends.
The worker reads the signed-in username’s saved phonebook description when a
conversation starts. Descriptions are updated explicitly through the phonebook
API. Conversation transcripts, call records, and summaries are not saved.
A connection failure, permission denial, missing worker, or lost connection is
shown in the UI. Leaving the page disconnects and releases the microphone.
Sessions end after `CONVERSATION_MAX_SECONDS` (default 30 minutes).

### Configuration and connection contract

`POST /api/v1/conversation/connect` requires the login cookie and accepts
`{"language_code":"en-IN","voice":"Shivani"}`. It returns `server_url`,
`participant_token`, `room_name`, and `participant_identity` with `no-store`.
Each call creates a unique room identity and signs a 10-minute join token,
restricted to that room and microphone publication. The token embeds explicit
worker dispatch to `opencall-conversation` with the validated voice/language and
the authenticated username. The worker reads that username’s description from
TinyDB. The browser calls the
same-origin `/api/conversation/connect` proxy to forward its session cookie.
LiveKit dispatches the worker when the participant joins. Provider keys and the
LiveKit API secret never reach the browser. Token expiry limits joining; the
worker's duration limit ends an already connected conversation.

`GROQ_MODEL` defaults to `openai/gpt-oss-20b`. Override it with another Groq
chat model available to your account. A real LiveKit Cloud deployment can use
`LIVEKIT_URL=wss://...`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` from that
project, with the backend and worker configured identically. The local development
key/secret are only for the loopback server. Conversation tokens are now protected
by the local demo login. Add real account provisioning, production cookie settings,
and per-user quotas/rate limits before exposing the service publicly.

Continuous conversation requires all four processes (room server, API, worker,
frontend). A passing health endpoint or issued token does not prove a worker has
joined or that provider audio works. Browser microphone and interruption behavior
must be verified with a real conversation.


### Continuous conversation validation

- 33 backend tests pass in the clean Python 3.13 environment; `pip check` passes.
- Frontend ESLint and TypeScript checks pass.
- Both dashboard pages return their expected HTML from the running development server.
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
