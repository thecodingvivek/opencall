# Phonebook and call memory

OpenCall remembers the signed-in caller across voice calls using TinyDB. The
current login identifier is a username; a stable `user_id` keeps the account's
memory independent of a later change to phone-number login.

## Data model

The ignored file `backend/data/opencall.json` contains these tables:

| Table | Identity | Stored data |
| --- | --- | --- |
| `users` | `user_id` | Username, display name, nullable phone number, password salt/hash |
| `sessions` | Hash of session token | User ID, expiry; existing username sessions remain valid until expiry |
| `phonebook` | `user_id` | Current username/phone number, short description, rolling previous summary, completed call count, revision, update time |
| `calls` | `call_id` | User ID, room, participant identity, timestamps, lifecycle and memory status, call summary, temporary text turns |

Phonebook response shape (timestamps are Unix seconds):

```json
{
  "user_id": "stable-internal-id",
  "username": "demo",
  "phone_number": null,
  "description": "A science teacher who prefers short answers in English.",
  "previous_summary": "Preparing a lesson about the moon for Friday.",
  "completed_calls": 1,
  "revision": 1,
  "updated_at": 1793036000.0
}
```

`description` contains durable facts about who the caller is (up to 800
characters). `previous_summary` carries useful context across calls: preferences,
goals, decisions, open questions and follow-ups (up to 4,000 characters). Each
completed spoken call also gets its own `call_summary` (up to 2,000 characters).
`completed_calls` counts calls successfully summarized, not empty room joins.

API startup backfills IDs for existing users without changing passwords or
invalidating existing sessions, then creates missing phonebook entries. Future
phone-number login should resolve to the same `users.user_id`; do not create a
new user or key memory by the phone number. Reading a phonebook syncs its current
username and phone number from `users`.

## Call flow

1. The browser sends settings to the same-origin Next.js
   `POST /api/conversation/connect` route. It forwards the HttpOnly session cookie
   to FastAPI. Anonymous/expired sessions receive `401`.
2. FastAPI derives the account from the session. A username or user ID supplied
   in the request body cannot select another account. It creates a call record
   and signs a room token containing only settings, call ID and participant
   identity in agent dispatch metadata; phonebook text stays out of this token.
3. The worker verifies that the dispatched call ID, room and participant match
   the persisted binding and activates it once. It attempts pending summaries
   for this account, then loads the latest phonebook before starting the agent.
4. The agent receives the profile and previous summary as background data. Its
   `lookup_phonebook` tool can fetch current memory again; the tool is bound to
   this user and accepts no arbitrary account identifier.
5. Committed user and assistant text turns are captured using LiveKit's
   `conversation_item_added` event. System messages, tool calls and audio are
   excluded. At most 200 recent turns / 60,000 text characters are retained,
   with each individual turn capped at 6,000 characters.
6. Session closure requests job shutdown immediately. A shutdown callback closes
   the session, marks the call ended and asks Groq for validated JSON memory.
   This covers End conversation, participant disconnect, duration expiry, and
   handled provider errors. No client "save transcript" request is required.
7. The phonebook and call status commit together. The call becomes `saved` and
   temporary turns are removed. The next call loads the updated memory. Calling
   finalization twice does not count or summarize a saved call again.

The summarizer merges existing memory with the latest call, uses only facts the
user states or confirms, and excludes credentials and unnecessary sensitive
details. Assistant suggestions are not treated as user facts. Both summarizer
and voice prompts identify stored text as untrusted data. These are model
instructions, not a guarantee of perfect extraction: summaries can contain
mistakes and should be inspected during development.

## Failure and concurrency behavior

- Calls with no user speech become `empty`; they do not change previous memory.
- Summary errors preserve the existing phonebook. The call becomes `failed`
  with only an error category and keeps bounded text for retry. Network,
  malformed JSON, oversized model output and incomplete responses are handled.
- Before a later call, the worker retries up to three pending/failed calls in
  ended order, with a 12-second overall startup budget. If time runs out, the
  new call uses the last successfully saved memory. The summary API request
  itself has a 12-second timeout. There is no background retry daemon.
- Concurrent calls use a phonebook revision check. If another call updates
  memory while summarization is in progress, the worker regenerates against the
  latest memory, up to three attempts. A late summary cannot silently overwrite
  a newer account revision.
- `app/core/database.py` serializes threads and processes with `RLock` and
  `fcntl.flock`. Each transaction reads fresh data and commits all table changes
  with an atomic file replacement. No network request runs while holding the
  database lock. This supports the local API and worker sharing one file;
  it is not distributed database storage.
- The worker allows 45 seconds for process shutdown so finalization can finish.
  A hard kill, machine crash or lost power can bypass callbacks. Already
  captured turns survive, but an `active` call interrupted this way is not
  automatically declared ended because another call could still be using it.
- A token that is issued but never joined leaves a `created` call. It does not
  update memory. There is currently no automatic cleanup or transcript expiry
  for failed/interrupted calls.

## Inspect the current account

After logging into the frontend, these same-origin GET routes use the browser's
existing cookie:

```text
GET /api/conversation/phonebook
GET /api/conversation/<call_id>
```

The corresponding FastAPI paths are `/api/v1/conversation/phonebook` and
`/api/v1/conversation/<call_id>`. They require its session cookie. Call status
returns only `call_id`, `status`, `started_at`, `ended_at`, `memory_status`, and
`call_summary`. Another account's call returns `404`; temporary turns and error
details are not exposed by the endpoint. All memory responses use `no-store`.

`memory_status` progresses from `waiting` to `pending`, then `saved` or `failed`;
calls without user speech use `empty`. Summaries are asynchronous after the
caller leaves, so poll call status to distinguish a completed update from one
still in progress. The dashboard's active transcript remains scoped to its tab.

## Configuration and verification

The API and worker must use the same absolute `TINYDB_PATH` on the same machine.
The existing `GROQ_API_KEY` and `GROQ_MODEL` also drive summarization; no new key
is required. Start the API, LiveKit server, worker, and frontend as described in
[README.md](README.md#run-locally). Restart a running worker after code changes.

```bash
cd backend
.venv-voice/bin/python -m unittest discover -s tests -v
cd ../frontend
bun run lint
bunx tsc --noEmit
bun run build
```

Tests cover session-derived ownership, cross-account isolation, token bindings,
legacy-user migration, persistence, worker context injection and shutdown,
idempotence, failed-summary recovery, overlapping calls, bounded inputs,
cross-process file locking and transaction rollback. Mock tests alone do not
prove provider quality, browser microphone behavior or a real disconnect.

Validation on October 26, 2026:

- All 48 backend tests passed; frontend lint, TypeScript and production build passed.
- Live frontend HTTP checks verified login enforcement, cookie forwarding,
  account-derived ownership, phonebook retrieval and call status.
- A live Groq check saved stated user facts and excluded an unconfirmed assistant
  suggestion using an isolated temporary database.
- Two real LiveKit calls with generated microphone audio exercised Gnani STT/TTS
  and Groq. The first saved a fictional caller's science-teacher profile and
  lesson summary after disconnect. The second recalled that context, then saved
  another summary. Both calls cleared their temporary turns; the account's
  summarized-call count reached two. The normal demo account was not given
  this test profile. Actual browser microphone/autoplay/echo remain separate checks.

References: [LiveKit events](https://docs.livekit.io/reference/agents/events/),
[Groq JSON output](https://console.groq.com/docs/structured-outputs).
