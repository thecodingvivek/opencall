# OpenCall frontend

The speech studio lives at `/dashboard`; `/` redirects there.

Start the FastAPI backend on port 8000 first (see `../backend/README.md`).
Then run from this directory:

```bash
bun install
bun run dev
```

Open http://localhost:3000/dashboard. Select the language you will speak, click
**Click to speak**, allow microphone access, and speak. Click **Stop & transcribe**
to send the recording and show the recognized text. Use **Copy text** to copy it.
Recordings stop automatically at 55 seconds. This is speech-to-text in the chosen
language, not translation into another language.

The app records with MediaRecorder, converts the audio to mono 16 kHz PCM WAV
using Web Audio, and sends it to `POST /api/v1/speech/transcribe` on FastAPI.
The `GNANI_API_KEY` belongs only in `backend/.env`.

The default backend address is `http://127.0.0.1:8000`. To override it, put
`NEXT_PUBLIC_API_URL=http://your-backend-address` in `.env.local`, then restart
Next.js. Configure the matching frontend origin in the backend's `CORS_ORIGINS`.
Microphone access requires localhost or HTTPS in a supported browser. For a remote
HTTPS frontend, use an HTTPS backend URL as well.

The page handles microphone denial, recording failures, processing, empty speech,
request timeouts, and backend errors. It releases the microphone after recording
and on navigation. Audio is sent to Gnani through the backend; transcripts are
kept in page memory and are not saved across reloads.

Checks:

```bash
bun run lint
bunx tsc --noEmit
bun run build
```
