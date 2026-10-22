# OpenCall backend

FastAPI HTTP backend with LiveKit Agents speech providers. Requires Python 3.11 or newer.

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

Use a dedicated virtual environment for this backend. If an older `.venv` also
contains Google ADK or LiteLLM, those unrelated packages can conflict with
LiveKit 1.8.8 dependencies; a fresh environment avoids that conflict.
Environment variables override
values in `backend/.env`; the app also works with the defaults without this file.

## Endpoints

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
The health endpoint checks only that the app responds; no database or authentication
is configured in this starter.

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

This migration uses LiveKit's speech framework inside the existing HTTP app.
It does not create a LiveKit room, WebRTC connection, agent worker, or LLM
conversation. No LiveKit Cloud URL/key/secret is needed for these endpoints.
A room-based realtime conversation would additionally require a worker,
room tokens/dispatch, and a frontend LiveKit connection.

References: [Gnani LiveKit plugin](https://docs.gnani.ai/livekit/introduction),
[Gnani TTS REST contract](https://docs.gnani.ai/api/TTS/tts-inference).

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
