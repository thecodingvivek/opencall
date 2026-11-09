# TinyDB to Supabase Postgres migration plan

Status: **proposal for review; not implemented**. Branch at review: `feat/cloud`.

## Goal and boundaries

Replace every runtime use of TinyDB with Supabase-hosted Postgres for the FastAPI API and LiveKit worker, preserving existing users, passwords, sessions, phonebook descriptions and API behavior. Move the actual data only after this plan is approved and a target Supabase project and cutover window are agreed. Do not expose credentials or user data in logs or commits.

This is a database migration, not an authentication-provider migration. Keep Firebase Google sign-in as it is and keep the existing local login and guest session contracts during this work. Today the `firebase_session` cookie is separate from `opencall_session`; Google sign-in does **not** authenticate the backend. Linking Firebase identities to backend accounts is a separate decision; never merge accounts based only on matching email or display name.

The supplied `backend/.agents/skills/supabase-server/SKILL.md` describes a TypeScript/Deno package for Supabase server functions. The existing API and worker are Python, so the proposed direct Postgres connection does not use that package or require a new Node/Edge service. If a later phase introduces `@supabase/server`, follow that skill and its package documentation.

## Current behavior and dependencies

- `backend/app/core/database.py`: file-locked TinyDB transactions and atomic replacement of `backend/data/opencall.json` (or `TINYDB_PATH`). Locks only coordinate processes sharing that local filesystem.
- `backend/app/services/auth.py`: `users` with username, display name, PBKDF2-SHA256 salt and hash; hashed opaque `sessions` with expiry; demo account seed and generated guest users. Raw session tokens live in `opencall_session` cookies, not in the database.
- `backend/app/services/phonebook.py`: one description per username, maximum 800 characters for API/model writes; LLM updates use compare-and-set to avoid overwriting a concurrent edit. Startup normalizes old records and may remove the old `calls` table.
- `backend/app/api/routes/auth.py` and `conversation.py`: login, logout, guest, current user, phonebook and conversation-token endpoints depend on those stores. `frontend/src/lib/auth.ts` and the Next.js proxies rely on their existing cookies and response shapes.
- `backend/app/voice_agent.py`: reads a user's phonebook from the worker process, then writes an updated description after the call. API and worker must point to the same Postgres database.
- `backend/app/services/conversation.py` includes `guest` in signed dispatch metadata, but `AuthStore.public_user()` currently returns only username and display name. Consequently newly created guests are not marked as guests in the dispatched metadata; guest-specific worker behavior should be tested and resolved explicitly during implementation, preserving the intended existing guest flow.
- `backend/app/main.py` initializes the stores at startup; configuration is in `backend/app/core/config.py` and `.env.example`. `backend/tests/test_auth.py`, `test_phonebook.py`, `test_conversation.py`, and `test_voice_agent.py` cover related behavior. Firebase session handling is in `frontend/src/app/api/firebase-session/route.ts`.

## Proposed architecture

Use a maintained Python Postgres driver, such as Psycopg 3 with a bounded connection pool, behind repository interfaces for authentication and phonebook operations. Keep the existing synchronous store interface initially: FastAPI's synchronous endpoints run in its thread pool, and the voice worker's post-call update already uses `asyncio.to_thread`. Move the worker's initial database read off its event loop as well. Give each API/worker process its own small pool, initialize it after process startup rather than before forking, close it on shutdown, and limit acquisition/connect timeouts. No network call should hold a database transaction open during LLM generation.

Use a private, non-Data-API-exposed schema, e.g. `opencall`, with narrowly scoped runtime roles and a separate migration role. If a schema is exposed through Supabase's Data API, explicitly revoke unintended grants and enable RLS with appropriate policies; a Postgres owner or bypass-RLS role can bypass RLS, so backend authorization and least-privilege grants remain mandatory. Do not place database credentials or Supabase secret keys in frontend code.

For persistent services, use Supabase's direct connection where network support permits, or the shared **session pooler** for IPv4-only hosts. For deployments that require transaction pooling, disable driver-side prepared statements and avoid session-bound state. Budget the combined pool size across API and worker processes. Configure TLS certificate validation and separate runtime and migration connection URLs via secret environment configuration. Connection details must be provided through local ignored environment files or a secret manager, never in chat or a committed file.

## Proposed data model

| Table | Columns and constraints | Purpose |
| --- | --- | --- |
| `opencall.users` | `username text primary key`, `display_name text not null`, `salt text not null`, `password_hash text not null` | Preserve existing username and PBKDF2 representation and compatibility. A future identity/guest column requires an explicit import/backfill strategy. |
| `opencall.sessions` | `token_hash text primary key`, `username text not null references users(username)`, `expires_at timestamptz not null` | Preserve opaque cookie tokens, hash-only storage, expiry and revocation. Index expiry for cleanup and username for account operations. |
| `opencall.phonebook` | `username text primary key references users(username)`, `description text not null default ''`, `revision bigint not null default 0` | Preserve account-scoped context and support atomic optimistic concurrency. Validate the 800-character limit on new writes; first audit old descriptions before adding a database check. |

Use unique constraints to handle guest-name races and retry collisions. Create a guest, its empty phonebook entry, and session in one transaction. Compare-and-set phonebook updates using `UPDATE ... WHERE username = ... AND revision = ... RETURNING ...` (or an equivalent comparison that preserves current semantics). A conflict must leave the newer edit intact. Handle expired sessions consistently and preserve case-sensitive username matching. Seed demo credentials only in an explicit local-development mode; do not silently seed them in a deployed database. Confirm desired demo-account behavior before cutover.

## Implementation stages after approval

1. **Inventory and safety.** Identify every TinyDB path and table actually used by all environments, current service topology and target Supabase project. Record only counts, schema shapes, duplicate/orphan counts, invalid records, description lengths and expiry distributions; do not print personal data, hashes, tokens or secrets. Identify old `calls` and other tables and obtain an explicit decision about retaining them; do not drop them merely because current code no longer uses them.
2. **Provision isolated test database.** Create version-controlled, reversible-forward SQL migrations with schema, constraints, indexes and restricted roles. Apply and exercise them in an isolated Supabase development project or a local Postgres test instance first. Separate migration credentials from runtime credentials; document network connectivity, TLS, pool sizes and failure behavior.
3. **Implement Postgres stores.** Replace `database.py`, TinyDB configuration and stores while preserving the existing public methods, API response shapes, login hashing, cookie names/lifetimes, session expiry and logout. Translate errors to safe client responses and do not expose SQL or credentials. Handle database outages with clear 503s rather than treating them as invalid credentials. Ensure unique guest creation, atomic guest/session/phonebook writes and concurrency-safe description updates. Resolve and test guest dispatch semantics before claiming parity.
4. **Build an offline import tool.** Read an explicit, protected TinyDB snapshot; validate and normalize users, sessions and phonebook entries without invoking constructors that mutate the source. Convert numeric Unix expiry values to UTC timestamps, retain salts/hashes unchanged, preserve token hashes for unexpired sessions, and create missing phonebook rows as current behavior requires. Skip expired sessions only if agreed; retain orphaned/duplicate/invalid records in a restricted audit report for manual resolution rather than silently deleting or merging. Never import raw tokens or log sensitive values. Use one transaction, deterministic keys and conflict checks; abort on mismatches. Support a non-mutating dry run, repeatable reconciliation and safe reruns; do not overwrite live changes on a rerun.
5. **Rehearse.** Take a restricted backup; restore a copy into a test environment. Run import, compare per-table counts and keyed integrity checks, verify expired-session treatment and a known test account/phonebook, and exercise concurrent updates and guest creation. Ensure no sensitive data is emitted to CI logs. Test against real Postgres, not only mocks.
6. **Cut over.** Schedule downtime: stop new writes and drain active API/worker sessions, then take the final source snapshot and backup. Apply migrations, import once, reconcile, configure both processes to the same target, start them and run smoke tests before allowing traffic. Preserve the snapshot and existing TinyDB implementation until acceptance. Avoid dual-write unless separately designed and tested.
7. **Retire TinyDB.** Only after acceptance remove the dependency, path setting, file-lock code, seed-on-start behavior and obsolete docs/tests. Search the whole repository for `tinydb`/`TINYDB_PATH`. Keep the backup under an agreed retention and access policy; do not delete it automatically.

## Verification and acceptance

- Unit and real-Postgres integration tests: login with existing PBKDF2 hashes, wrong password and unknown user, session persistence across restart, expiry, logout, guest uniqueness under concurrency, and atomic guest provisioning.
- Verify user isolation for `/me`, phonebook GET/PUT and conversation dispatch; ensure missing/expired/forged cookies are rejected, database failures fail closed and errors do not reveal sensitive details.
- Check that simultaneous manual edits and worker-generated updates do not overwrite one another. Test worker startup, job dispatch, shutdown update, guest behavior, and API/worker running as separate processes against one database.
- Confirm migration counts and referential integrity, compare imported test descriptions and unexpired session behavior without disclosing values, test dry run and a second import, and run existing speech/weather/observability regressions.
- Run `bun`-based frontend checks and browser tests for existing login, guest `/try`, phonebook, logout and continuous voice; separately validate live LiveKit/Gnani/Groq and Phoenix boundaries. Firebase Google sign-in is not evidence of backend authentication.
- Acceptance requires successful tests on the selected Supabase environment, verified reconciliation, and a real end-to-end call. Document what was tested and what remains unverified.

## Rollback and decisions before execution

Rollback is possible only with an explicit write freeze: stop traffic and workers, preserve a Postgres snapshot/export of all post-cutover writes, and decide how to reconcile those writes before restarting the old TinyDB version. Restoring the old JSON alone would lose accounts, sessions and descriptions written after cutover. If reconciliation cannot be done safely, keep traffic stopped and resolve it rather than silently discarding data.

Please review these choices before implementation:

1. Which Supabase project and environments should be used, and is a separate test project available?
2. Should existing login sessions remain valid after migration? The plan preserves unexpired session hashes and cookie names by default.
3. Should the local demo account remain available outside local development? Recommended: no.
4. What retention and cleanup policy should apply to generated guest accounts, historical tables and the TinyDB backup? No automatic deletion is proposed.
5. Should Firebase Google users eventually be linked to backend accounts? This plan deliberately does not perform that separate identity migration.

## References

- [Supabase Postgres connection modes and limitations](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase: securing data](https://supabase.com/docs/guides/database/secure-data)
- [Supabase row-level security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [`@supabase/server` skill](backend/.agents/skills/supabase-server/SKILL.md)
