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
Click the speaker **Listen** button beside **Copy text** to hear the transcript
using Gnani TTS. While audio is playing, click **Stop**; click **Play** to replay it.
Use the **Voice** dropdown to choose from 13 Timbre v3.0 multilingual voices. Voice
options load from the backend's `/api/v1/speech/voices` endpoint. Changing the
voice stops any current audio and regenerates it on the next **Listen** click.
Use **Delivery** for Neutral, Excited, Whispering, Shouting, and the other
supported delivery cues. Changing delivery also resets the audio. This changes
how the transcript is spoken; it does not rewrite the visible transcript.
If your browser blocks automatic playback, click **Play** once audio is ready.
Playback uses the transcript's recorded language even if you change the selector
afterward, and stops when a new recording begins or you leave the page.
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
