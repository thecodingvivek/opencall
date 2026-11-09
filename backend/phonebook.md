# Phonebook

The phonebook has one entry per username, with a description and language preference:

```json
{
  "username": "demo",
  "description": "A science teacher who prefers short answers.",
  "preferred_language": "hi-IN"
}
```

It is stored in the `phonebook` column of `opencall.users` in Supabase Postgres.
New accounts receive an empty description.

## Read and update

Both endpoints require the login cookie. The username comes from the session.

```text
GET /api/v1/conversation/phonebook
PUT /api/v1/conversation/phonebook
```

PUT accepts only the description (up to 800 characters):

```json
{"description": "A science teacher who prefers short answers."}
```

GET and PUT return the complete entry. An empty description clears it.
The frontend proxies these requests through `/api/conversation/phonebook`.

## Agent behavior

When a conversation starts, the backend passes the authenticated username in
signed LiveKit dispatch metadata. The worker reads that username's phonebook
entry and includes the description in the assistant's instructions as background data.
When the session ends, the worker closes the voice session and sends the existing
description plus the user's spoken messages to Groq. It merges useful facts,
preferences, goals and ongoing context into a description of at most 800 characters.
The caller's selected language is saved separately as `preferred_language` when selected.
Messages stay in session memory and are not written to the database.

Empty sessions skip the update. Provider errors, invalid output, or a newer
concurrent edit preserve the current description. There is no background retry.
Updates take a few seconds after disconnect, so wait briefly before checking GET.
A hard kill can skip the shutdown callback. Model extraction can make mistakes.
PUT remains available for explicit edits.

## Database configuration

The API and worker must use the same Supabase Postgres database and apply
`backend/migrations/001_users.sql` and `backend/migrations/004_preferred_language.sql` before use. The `phonebook_revision` column
protects an explicit edit from being overwritten by an older generated update.
