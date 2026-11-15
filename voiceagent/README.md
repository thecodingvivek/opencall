# OpenCall voice agent

The worker entry point is `voiceagent/worker.py`. FastAPI runs separately. The worker currently shares configuration, provider adapters, phonebook storage, weather tools with `backend/`; build and deploy from the **repository root**, where the Dockerfile lives.

## Local development

From the repository root:

```sh
PYTHONPATH=backend backend/.venv-voice/bin/python -m voiceagent.worker dev
```

`bun run dev` starts the worker using this entry point alongside the API/frontend.

## LiveKit Cloud

Authenticate with `lk cloud auth` or provide project credentials in ignored `voiceagent/.env`, then use the deployment helper below. The helper isolates Python files from the Node project at the root. The dispatch name is `opencall-conversation`; configure the FastAPI backend with credentials for that same LiveKit project. API/frontend hosting is separate from agent deployment.

`bun run dev` always uses the local LiveKit server and laptop worker. It does not load `voiceagent/.env`. For a production API, set `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in the API host's environment to the same cloud project; deploy the worker separately to LiveKit Cloud. The deployment helper reads `voiceagent/.env` only for deployment. Restart existing processes after changing configuration.

Current deployment: `CA_7NzcFASvDmtZ`, region `ap-south` (Mumbai), dispatch name `opencall-conversation`. The new project's agent has registered and its replica is running; an authenticated browser conversation has not yet been verified. When `backend/.env` contains `poolurl`, the helper uses it unless an explicit `DATABASE_URL` overrides it. Use `--secrets-only` to update worker secrets without rebuilding; LiveKit restarts the agent.

The Dockerfile runs Python 3.13 as an unprivileged user, downloads model files during build and launches `python -m voiceagent.worker start`.

Supply worker secrets via LiveKit: `GNANI_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, optional `GEOAPIFY_API_KEY` for nearby farming places, and any model overrides. LiveKit injects its own `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`. Mount `backend/prod-ca-2021.crt` with LiveKit's secret-file mechanism and set `DATABASE_SSL_ROOT_CERT=/etc/secrets/prod-ca-2021.crt`. No Firebase service-account key is required by the worker; authentication remains in the API.

Set `GROQ_FALLBACK_API_KEY` to an optional second Groq key. Voice replies try the primary model with each key before trying the configured fallback model with each key. Phonebook summaries retry with the second key on connection, timeout, authentication, rate-limit, or server errors. Both keys can still fail, and a shared account quota or provider outage can affect both.

With cloud keys in ignored `voiceagent/.env`, deploy using `backend/.venv-voice/bin/python voiceagent/deploy.py --region REGION`. This stages a Python-only build context (avoiding detection of the frontend Node project), reads the provider/database values from the backend environment, uploads only the required values through a restricted temporary file, and mounts the certificate. The generated `livekit.toml` is copied back to the repository root. For subsequent deployments add `--update`. It does not copy Firebase credentials or change the API's LiveKit configuration.

Keep all environment files, credentials, database certificates and local data out of the build context. Check `lk agent status` and logs after deployment, then test a real authenticated browser call and confirm phonebook persistence. A successful build alone does not establish audio behavior.
