# Phonebook

The phonebook has one entry per username, with exactly two fields:

```json
{
  "username": "demo",
  "description": "A science teacher who prefers short answers."
}
```

It is stored in the `phonebook` table inside `backend/data/opencall.json`.
New accounts present at startup receive an empty description.

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

GET and PUT return the complete two-field entry. An empty description clears it.
The frontend proxies these requests through `/api/conversation/phonebook`.

## Agent behavior

When a conversation starts, the backend passes the authenticated username in
signed LiveKit dispatch metadata. The worker reads that username's phonebook
entry and includes the description in the assistant's instructions as background data.
When the session ends, the worker closes the voice session and sends the existing
description plus the user's spoken messages to Groq. It merges useful facts,
preferences, goals and ongoing context into a description of at most 800 characters.
Only the updated description is saved; the phonebook still has exactly two fields.
Messages stay in session memory and are not written to the database.

Empty sessions skip the update. Provider errors, invalid output, or a newer
concurrent edit preserve the current description. There is no background retry.
Updates take a few seconds after disconnect, so wait briefly before checking GET.
A hard kill can skip the shutdown callback. Model extraction can make mistakes.
PUT remains available for explicit edits.

## Existing local data

On startup, existing descriptions are preserved and phonebook rows are reduced
to `username` and `description`. The old `calls` table is removed. Extra account
IDs and phone-number placeholders are removed from users; existing login sessions
are converted to username-based sessions. No call history or summaries are retained.

The API and worker must use the same `TINYDB_PATH`. Restart a running worker
after applying this change.
