# Agent observability with Phoenix

This folder contains OpenCall's tracing configuration, local Phoenix runner,
dependencies, and trace helpers. The agent and phonebook service only call these
helpers; the observability setup stays here.

## Start

The backend environment must have the updated requirements:

```bash
cd backend
.venv-voice/bin/python -m pip install -r requirements.txt
cd ..
bun run dev
```

The launcher starts the local Phoenix collector before the voice worker. Open
**http://localhost:6006**, select the **opencall** project, and make a voice call.
Allow a few seconds for batched spans to appear. End the call to see the complete
session and its description update.

To run only Phoenix from `backend/`:

```bash
.venv-voice/bin/python -m observability.server
```

Phoenix binds to loopback and stores its SQLite database in the ignored
`observability/data/` directory. This database is separate from the application's
TinyDB phonebook. The runner disables Phoenix's bundled assistant and verbose
migration logging; those features are not needed for collecting OpenCall traces.

## What is traced

| Trace/span | What it shows |
| --- | --- |
| `opencall.session` | Full session duration, username, room/session ID, language and voice. |
| LiveKit spans | Session startup, voice pipeline, turn handling, interruption and provider timings. |
| OpenAI SDK spans | OpenAI-compatible Groq requests, model information, token usage and failures. |
| `phonebook.update_description` | Description update outcome: updated, unchanged, no speech, or failed. |
| `phonebook.generate_description` | Groq description-generation latency, model, token usage and errors. |

The worker attaches native LiveKit tracing and OpenAI instrumentation to the
Phoenix provider. OpenCall's session span stays open until the session closes
and the description update finishes. Spans carry `session.id` and `user.id`,
so a call and its description update can be followed together. On shutdown,
the worker ends the session span and flushes queued traces.

The pipeline looks like this (exact LiveKit span names depend on the SDK):

```text
opencall.session
├── LiveKit session, turn and speech spans
│   └── Groq/OpenAI SDK LLM spans
└── phonebook.update_description
    └── phonebook.generate_description
```

Handled description-update errors are explicitly marked as trace errors even
though the application keeps the previous description and continues normally.
Tracing initialization failure does not stop a voice session.

## Configuration

Settings are read from `backend/.env` by `observability/config.py`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `PHOENIX_ENABLED` | `true` | Enable tracing and automatic local collector startup. |
| `PHOENIX_PROJECT_NAME` | `opencall` | Project displayed in Phoenix. |
| `PHOENIX_COLLECTOR_ENDPOINT` | `http://127.0.0.1:6006/v1/traces` | HTTP OTLP destination. |
| `PHOENIX_PORT` | `6006` | Local UI/collector port; update the endpoint too if changed. |
| `PHOENIX_CAPTURE_CONTENT` | `false` | Include prompt, reply and description text in traces when enabled. |

By default, traces include timing, model/token information, outcomes, username
and session labels, while conversational input/output text is hidden. Set
`PHOENIX_CAPTURE_CONTENT=true` to inspect that text in Phoenix. It is then
persisted in Phoenix's trace database, independently of the two-field phonebook.
This integration does not add audio recording or trace API keys/passwords.

Restart the launcher and worker after changing tracing settings. Set
`PHOENIX_ENABLED=false` to run without this integration. A remote collector
endpoint skips automatic local Phoenix startup; remote authentication is not
configured by this local setup.

## Files

- `config.py`: environment settings.
- `tracing.py`: provider setup, session metadata, OpenAI instrumentation, custom spans and flush handling.
- `server.py`: local collector/UI process and storage location.
- `requirements.txt`: Phoenix and instrumentation dependencies, included by backend requirements.
- `data/`: generated local traces and server data; ignored by Git.

References: [LiveKit OpenTelemetry traces](https://docs.livekit.io/testing/observability/tracing/),
[Phoenix Python tracing setup](https://arize.com/docs/phoenix/resources/python-api).
