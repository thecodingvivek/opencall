# OpenCall voice agent

The worker entry point is `voiceagent/worker.py`. FastAPI runs separately. The worker currently shares configuration, provider adapters, phonebook storage, weather tools and tracing with `backend/`; build and deploy from the **repository root**, where the Dockerfile lives.

## Local development

From the repository root:

```sh
PYTHONPATH=backend backend/.venv-voice/bin/python -m voiceagent.worker dev
```

`bun run dev` starts the worker using this entry point alongside the API/frontend.

## LiveKit Cloud

Authenticate with `lk cloud auth` or provide project credentials in ignored `voiceagent/.env`, then use the deployment helper below. The helper isolates Python files from the Node project at the root. The dispatch name is `opencall-conversation`; configure the FastAPI backend with credentials for that same LiveKit project. API/frontend hosting is separate from agent deployment.

Set `VOICE_AGENT_REMOTE=true` in the API's `backend/.env` once the cloud agent is healthy, so `bun run dev` does not register a second local worker alongside the cloud worker. Set the API's `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` to that cloud project.

Local settings also read `voiceagent/.env` after `backend/.env`, so cloud keys stored there are shared with the API. `VOICE_AGENT_REMOTE=true` there skips the local worker. Restart existing API/dev processes after changing these values.

Current deployment: `CA_f2xynEedv2Bv`, region `ap-south` (Mumbai), dispatch name `opencall-conversation`. The Supabase session pooler is used for IPv4 connectivity. A synthetic room test verified cloud dispatch, database-backed startup and receipt of greeting audio; real browser microphone and playback remain unverified. When `backend/.env` contains `poolurl`, the helper uses it unless an explicit `DATABASE_URL` overrides it. Use `--secrets-only` to update worker secrets without rebuilding; LiveKit restarts the agent.

The Dockerfile runs Python 3.13 as an unprivileged user, downloads model files during build and launches `python -m voiceagent.worker start`. Phoenix is disabled in the image by default; configure a reachable remote collector before enabling it.

Supply worker secrets via LiveKit: `GNANI_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, and any model overrides. LiveKit injects its own `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. Mount `backend/prod-ca-2021.crt` with LiveKit's secret-file mechanism and set `DATABASE_SSL_ROOT_CERT=/etc/secrets/prod-ca-2021.crt`. No Firebase service-account key is required by the worker; authentication remains in the API.

With cloud keys in ignored `voiceagent/.env`, deploy using `backend/.venv-voice/bin/python voiceagent/deploy.py --region REGION`. This stages a Python-only build context (avoiding detection of the frontend Node project), reads the provider/database values from the backend environment, uploads only the required values through a restricted temporary file, and mounts the certificate. The generated `livekit.toml` is copied back to the repository root. For subsequent deployments add `--update`. It does not copy Firebase credentials or change the API's LiveKit configuration.

Keep all environment files, credentials, database certificates and local data out of the build context. Check `lk agent status` and logs after deployment, then test a real authenticated browser call and confirm phonebook persistence. A successful build alone does not establish audio behavior.
