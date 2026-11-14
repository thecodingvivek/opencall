# OpenCall frontend

Run the application from the repository root:

```bash
bun install
bun run dev
```

Open http://localhost:3000, sign in with Google, and start a voice conversation
on `/try`. Microphone access requires localhost or HTTPS. The local launcher
starts the frontend, API, LiveKit server and voice worker; see
[backend setup](../backend/README.md) for provider and database configuration.

For deployment, set `API_URL` to the public FastAPI origin. The frontend does
not hold a Firebase service-account key: the browser's Google ID token is sent
to the backend (`POST /api/v1/auth/session`), which verifies it, creates the
session cookie and syncs the account. Configure the key only on the backend
with `FIREBASE_SERVICE_ACCOUNT_JSON` or `FIREBASE_SERVICE_ACCOUNT_PATH`, then
redeploy. Never commit the key file. Logging out calls
`POST /api/v1/auth/logout`, which revokes the user's Firebase sessions.

To run frontend checks:

```bash
cd frontend
bun run lint
bunx tsc --noEmit
bun run build
```
