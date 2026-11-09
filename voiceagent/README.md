# OpenCall voice agent

The worker entry point is `voiceagent/worker.py`. FastAPI runs separately. The worker currently shares configuration, provider adapters, phonebook storage, weather tools and tracing with `backend/`; build and deploy from the **repository root**, where the Dockerfile lives.

## Local development

From the repository root:

```sh
PYTHONPATH=backend backend/.venv-voice/bin/python -m voiceagent.worker dev
```

`bun run dev` starts the worker using this entry point alongside the API/frontend.

## LiveKit Cloud

Authenticate with `lk cloud auth`, select the correct project, then run `lk agent create` from the repository root. For later versions use `lk agent deploy`. The dispatch name is `opencall-conversation`; configure the FastAPI backend with credentials for that same LiveKit project. API/frontend hosting is separate from agent deployment.

Set `VOICE_AGENT_REMOTE=true` in the API's `backend/.env` once the cloud agent is healthy, so `bun run dev` does not register a second local worker alongside the cloud worker. Set the API's `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` to that cloud project.

The Dockerfile runs Python 3.13 as an unprivileged user, downloads model files during build and launches `python -m voiceagent.worker start`. Phoenix is disabled in the image by default; configure a reachable remote collector before enabling it.

Supply worker secrets via LiveKit: `GNANI_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, and any model overrides. LiveKit injects its own `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. Mount `backend/prod-ca-2021.crt` with LiveKit's secret-file mechanism and set `DATABASE_SSL_ROOT_CERT=/etc/secrets/prod-ca-2021.crt`. No Firebase service-account key is required by the worker; authentication remains in the API.

Keep all environment files, credentials, database certificates and local data out of the build context. Check `lk agent status` and logs after deployment, then test a real authenticated browser call and confirm phonebook persistence. A successful build alone does not establish audio behavior.
