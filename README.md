# OpenCall

Continuous voice conversations with LiveKit, Gnani streaming speech, and Groq.

Open the home page and sign in with Google to reach `/try`. Start a conversation,
speak naturally, and interrupt the assistant by speaking.

See [backend setup](backend/README.md#continuous-voice-conversations) for the
LiveKit server, Python 3.13 agent worker, API, environment variables, and validation.
Run the Next.js frontend with `bun install` and `bun run dev` from `frontend/`.

## LiveKit Cloud deployment

The GitHub Actions workflow in `.github/workflows/deploy-livekit.yml` tests the
backend and deploys the voice agent when relevant files are pushed to `main`.
It can also be run manually from the Actions tab on `main`. Frontend-only changes
and documentation do not trigger a voice deployment. Deployments are serialized;
the workflow waits until LiveKit reports the exact commit and a running replica.

The repository requires these GitHub Actions secrets for deployment:
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`. They authenticate
GitHub to LiveKit Cloud. Gnani, Groq, database credentials, and the database
certificate remain configured on the LiveKit agent; this workflow does not replace
them. The build context excludes local environment files and certificates.

Check the workflow run in GitHub Actions and the agent in LiveKit Cloud after a
push. A running replica confirms startup, not that a real voice conversation or
crop search has succeeded. To recover from a bad release, revert the change on
`main` and allow the workflow to deploy the revert.
