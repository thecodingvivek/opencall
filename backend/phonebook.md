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
Descriptions are saved explicitly through PUT; they are not generated after calls.

## Existing local data

On startup, existing descriptions are preserved and phonebook rows are reduced
to `username` and `description`. The old `calls` table is removed. Extra account
IDs and phone-number placeholders are removed from users; existing login sessions
are converted to username-based sessions. No call history or summaries are retained.

The API and worker must use the same `TINYDB_PATH`. Restart a running worker
after applying this change.
