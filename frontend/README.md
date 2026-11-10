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

For deployment, set `API_URL` to the public FastAPI origin and set
`FIREBASE_SERVICE_ACCOUNT_JSON` to the full Firebase service-account JSON as a
server-side secret. The backend also needs that secret, or a secure credential
file configured with `FIREBASE_SERVICE_ACCOUNT_PATH`. Configure these variables
on each respective hosting project, then redeploy. Never commit the key file.

To run frontend checks:

```bash
cd frontend
bun run lint
bunx tsc --noEmit
bun run build
```
