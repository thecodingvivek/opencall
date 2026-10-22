# OpenCall

Continuous voice conversations with LiveKit, Gnani streaming speech, and Groq.

Open `/dashboard` to start a conversation, speak without pressing a button for
each turn, and interrupt the assistant by speaking. The recording/transcription
studio is available at `/dashboard/transcribe`.

See [backend setup](backend/README.md#continuous-voice-conversations) for the
LiveKit server, Python 3.13 agent worker, API, environment variables, and validation.
Run the Next.js frontend with `bun install` and `bun run dev` from `frontend/`.
