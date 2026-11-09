# TinyDB to Supabase Postgres migration plan

Status: **proposal for review; not implemented**. Branch at review: `feat/cloud`.

## Revised plan: fresh users, Google identity, phone and phonebook

- Start fresh in Supabase: **do not import any TinyDB users, passwords, sessions or phonebook descriptions**. Existing local accounts and sessions will not work after cutover. This does not delete Firebase Authentication accounts or the old TinyDB file; actual deletion requires a separate decision.
- Google sign-in is required for every user, including “try without number.” After sign-in, verify the Firebase identity server-side and sync the user to Postgres using the verified Firebase UID. The current Firebase cookie is separate from backend auth, so this connection needs to be implemented.
- Store the user's entered phone number on their user record, initially marked **unverified**. If they select “try without number,” assign a unique random placeholder. A generated number is not an owned or callable phone number and must never be used for calls, SMS or verification. Recommended: keep the real `phone_number` nullable and use a separate `generated_phone_identifier` column, rather than mixing fake numbers with real ones.
- Store `phonebook` as a **text column on the user row**, initially empty. Both manual edits and the voice worker update it, using a revision column and an atomic compare-and-set so a generated update cannot overwrite a newer edit. Preserve the current 800-character bound.

### Revised schema

One private `opencall.users` table: `id` (UUID primary key), `firebase_uid` (unique), optional `display_name` and `email`, nullable `phone_number`, `phone_verified` (default false), nullable unique `generated_phone_identifier`, `phonebook` (non-null text, default empty), `phonebook_revision` (integer), and creation/update timestamps. During incomplete onboarding neither phone field may be set; after selection, use one or the other. Generate placeholders with a unique constraint and retry collisions; repeated onboarding must not replace an existing value. Firebase session cookies provide the session, so no Postgres sessions table is needed unless later required. A real phone number's country/format and ownership verification still need a product decision.

### Revised implementation sequence

1. Provision an isolated Supabase test database and version-controlled schema; use private tables, restricted runtime credentials, verified TLS and bounded Python Postgres pools for both API and worker. Keep credentials server-side.
2. Verify Firebase identity server-side and atomically upsert each signed-in user by Firebase UID before onboarding continues. Sync display name and email from verified claims when available; preserve phone, placeholder, phonebook and creation date on subsequent sign-ins. If the sync fails, show a retryable error. Update the Next.js proxies and protected API routes to use that identity; add logout and expiry handling. Never match accounts solely on email or phone number.
3. Wire the existing phone input and Continue button. Validate the entered number, mark it unverified, and store it. For no-number onboarding, require Google sign-in, create one unique placeholder and reuse it on repeat requests. Allow a deliberate later replacement with a real number.
4. Replace TinyDB phonebook access with the `phonebook` column. Pass the stable user ID through signed LiveKit dispatch metadata. Have the worker read the matching user and atomically update the phonebook after a call, without holding a transaction open during LLM generation. Correct and test the current guest-flag behavior.
5. Test Google sign-in and cookies, identity isolation, missing/forged/expired sessions, number handling and placeholder collisions, concurrent phonebook edits, real Postgres transactions, API/worker coordination, and browser/LiveKit provider boundaries. Remove old local auth, TinyDB dependency, storage code and configuration only after acceptance.
6. Cut over to an empty user table after stopping writes and draining calls. Retain a protected TinyDB snapshot for rollback; do not import it or automatically delete it. Rollback must preserve Postgres writes made after cutover and requires a separate reconciliation decision.

### Decisions to confirm before implementation

1. Which country/number formats should be accepted, and is phone ownership verification required now?
2. Is a separate `generated_phone_identifier` field acceptable for the fake number? This prevents treating it as a callable number.
3. Which Supabase project and test environment should be used, and how long should the old TinyDB data be retained?

The supplied `backend/.agents/skills/supabase-server/SKILL.md` covers TypeScript and Deno server functions. The current API and worker are Python, so the plan uses a direct Postgres connection; the skill applies if that package is introduced later.

