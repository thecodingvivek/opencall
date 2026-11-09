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

To run frontend checks:

```bash
cd frontend
bun run lint
bunx tsc --noEmit
bun run build
```
