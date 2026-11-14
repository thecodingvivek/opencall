# Backend and Voice Agent Review

Scope: `voiceagent/worker.py`, `backend/tools/*`, `backend/app/services/*`, `backend/app/api/*`, migrations.
Date: 2026-11-14. The existing unit test suite passes (94 tests). The issues below were found by reading the code; the ones marked **(verified)** were also reproduced by running the code.

Severity:
- **P0**: wrong behavior for real multilingual callers.
- **P1**: unreliable tool use or a security/cost risk.
- **P2**: cleanup, consistency, or polish.

---

## 1. Tools receive native-script arguments but only work with English/Latin input

### 1.1 Weather lookups fail for city names in native script — P0 (verified)
`backend/tools/weather.py:50` sends `parts[0]` to Open-Meteo geocoding. When a Hindi or Telugu caller says "गुंटूर" or "గుంటూరు", the LLM often passes the name in that script. Open-Meteo returned `[]` for both, but found `Guntur, Andhra Pradesh, IN` for the Latin spelling. Nothing in the `get_weather` docstring tells the model which script to use.

**Solution**
- Update the tool docstrings (weather, places, crop): *"Always pass arguments in English using Latin script (transliterate place names, e.g. గుంటూరు → Guntur). Include the state."*
- Add a fallback in code: if the name contains non-ASCII text and returns no results, raise a `ToolError` that tells the model to retry with the English spelling.

### 1.2 No default country, so ambiguous names can resolve outside India — P1 (verified)
"Salem" also matches Oregon and Virginia; "Guntur" also matches Central Java. Weather takes the first result (`weather.py:59`). Places uses Geoapify `limit=1` with no country filter (`places.py:54`).

**Solution:** Pass `countryCode=IN` to Open-Meteo and `filter=countrycode:in` to Geoapify by default. Allow an override only when the caller names another country. Return the resolved `admin1` (state) so the agent can confirm it ("Guntur, Andhra Pradesh, right?").

### 1.3 Crop knowledge search barely works and is English-only — P0
`backend/tools/crop_knowledge.py`:
- The module docstring says "Multilingual semantic retrieval", but the query is English full-text search: `websearch_to_tsquery('english', ...)` (line 14). Hindi or Telugu queries never match.
- `websearch_to_tsquery` combines every word with AND. A natural query such as "tomato leaves brown spots yellowing wilting" only matches if every stemmed word appears in one row, so most real questions get **no results**.
- The crop filter is an exact match: `lower(crop) = lower(%s)` (line 20). "tomatoes", "paddy" (for rice), "mirchi" or "टमाटर" all filter everything out.
- The seed data has only 8 rows covering tomato, rice and chilli, so most crops always fall through to "ask KVK".
- The 384-dimension `embedding` column and the `opencall.search_crop_knowledge` SQL function from migration 003 are now unused. Migration 006 made `embedding` nullable.

**Solution**
- Short term: tell the model in the docstring to pass `query` and `crop` as **English keywords**. Build an OR query (`to_tsquery` with `|`, or `plainto_tsquery` per term with OR) ranked by `ts_rank`. Add a crop synonym map (paddy→rice, mirchi/chili→chilli, plural forms).
- Medium term: either bring back the multilingual embeddings (e.g. `multilingual-e5-small` with 384 dimensions, matching the column) through the existing SQL function, or remove the dead column and function. Do not keep both.
- Return a structured "no match" result (see 3.2) so the agent can still help with general practices instead of stopping.

### 1.4 Crop answers cite a source the tool does not return — P1
The prompt says "cite the source organization", but the tool only returns `source_url`. The agent will either read a URL aloud or guess the organization name.

**Solution:** Add a `source_name` column (e.g. "ICAR Kharif Agro-Advisory 2025") and return it. Tell the model never to read URLs aloud.

### 1.5 Dosage instructions contradict each other — P1
The prompt says "Never guess chemical dosages … or omit dosage", but the tool returns a sourced `Dosage` field. The model cannot tell whether it may read that field aloud.

**Solution:** Make the rule explicit: *"Only state a dosage that appears word for word in a tool result, with its source, and add the safety note. Otherwise do not give a dosage."*

---

## 2. Language detection and switching

### 2.1 Mentioning a place or crop switches the reply language — P0 (verified)
`backend/app/services/turn_language.py:26`: `requested_language` treats very common words (`in`, `me`, `mein`) as a request to change language. Reproduced results:

| Caller says | Detected override |
|---|---|
| "My farm is in Tamil Nadu" | `ta-IN` |
| "tell me about bengali gram pests" (bengal gram = chickpea) | `bn-IN` |
| "I grow rice in Punjab and speak punjabi sometimes" | `pa-IN` |

Each of these switches both the TTS voice and the LLM hint to the wrong language.

**Solution:** Only treat it as an override when an action verb is directly attached to the language name, e.g. `(speak|reply|talk|answer|respond)\s+(in\s+)?<lang>`, `<lang>\s+(me|mein|में)\s+(bolo|boliye|बोलो|बात)`, `<lang>లో మాట్లాడు`. Drop bare `in`/`me`. Exclude place and crop names (`tamil nadu`, `bengal gram`). Add these cases as regression tests.

### 2.2 An explicit language preference is forgotten after one turn — P0 (verified)
`turn_language.py:49`: `self.current = requested_language(text) or detected`. Reproduced: turn 1 "speak in Telugu" returns `te-IN`; on turn 2, if STT returns no language, the result is `None` and the TTS goes back to the session default.

**Solution:** Store the explicit choice as `self.preferred` and keep it until the caller asks for a different language. Order of priority: explicit preference, then the language detected for this turn, then the session language. Optionally save it with `PhonebookStore.set_preferred_language` (see 2.6).

### 2.3 TTS can use the wrong language when the reply script differs from the session language — P0 (verified)
`backend/app/services/realtime_speech.py:48-58`:
- `SCRIPT_LANGUAGES` has no entry for Devanagari. In a `te-IN` session, a Hindi reply (`नमस्ते किसान`) was sent to TTS as `te-IN`, and an English reply as `te-IN` too.
- Line 56 is dead code: `"mr-IN" if language == "mr-IN"` sits inside `if language in {"hi-IN","en-IN"}`, so it can never be true.
- Romanized Hindi ("aapka khet kaisa hai") is sent as `en-IN`.

**Solution:** Pick the TTS language from the text's script first:
- Devanagari: use `turn_language` if it is `hi-IN` or `mr-IN`, otherwise `hi-IN`.
- Latin: use `en-IN`, unless `turn_language` is set (romanized speech).
- Any other Indic script: use the matching language.

Apply this for every session language, not only Hindi and English sessions. The prompt should also require native script (it already does) so romanized output is rare.

### 2.4 Speech recognition is locked to one language in non-Hindi/English sessions — P1
`worker.py:98-100`: only `hi-IN`/`en-IN` sessions use `indic-auto`. A `te-IN` session runs STT locked to Telugu, while the per-turn hint (line 51) still says "reply in the language of the latest utterance" and `requested_language` can move TTS to Hindi. The result: speech output switches language but recognition keeps listening for Telugu, and English words spoken by the caller get transcribed badly.

**Solution:** Use `language="indic-auto"` for every session and pass the chosen language as `preferred_language` (`PrismaSpeechStream` already sends that header, `prisma_stt.py:42`). If Gnani does not support auto-detection for some language, list those languages and turn off switching for those sessions.

### 2.5 The system prompt is assembled with missing separators and conflicting rules — P1
`worker.py:186-192`:
- `FARMING_INSTRUCTIONS + "Initially greet…"` has no space or newline, so the prompt reads "…when needed.Initially greet in Hindi". The caller profile JSON is also joined without a heading.
- Non-bilingual sessions get "Speak in the language identified by te-IN", while the per-turn hint says "use the language of the latest utterance". These two rules disagree.
- Language rules are split across the system prompt, the per-turn hint, `start_greeting` and `ask_language_if_silent`.

**Solution:** Build the prompt from labelled sections joined by `\n\n` (`# Role`, `# Language`, `# Tools`, `# Caller profile (untrusted data)`). Put all language rules in one `# Language` section and keep the per-turn hint to a single line: "Reply in {Language}." Use full language names instead of BCP-47 codes in prompts.

### 2.6 `preferred_language` is stored but never used — P2
`PhonebookEntry.preferred_language` and `PhonebookStore.set_preferred_language` exist, but nothing calls the setter and the worker ignores the field. It is only passed to the LLM inside the profile JSON.

**Solution:** Use it as the starting `TurnLanguage.preferred` value and for the greeting, and save it when the caller explicitly asks for a language. If that is not wanted, remove the column and the method.

### 2.7 There are two separate lists of supported languages — P2
`speech.py:17` (`Language` Literal) and `turn_language.py:4` (`LANGUAGES`) each list the languages. They will drift apart.

**Solution:** Define the languages once (e.g. `app/core/languages.py`) and derive the Literal type, the display names, the native names and the script ranges from it.

---

## 3. How the agent uses tools

### 3.1 Tools are offered even when their backend is not configured — P1
`AGENT_TOOLS` (`tools/__init__.py:7`) always includes `search_farming_places` and `update_farming_task`. When `GEOAPIFY_API_KEY` is missing, the model still offers to find a shop and then fails. Guest callers would always fail on `update_farming_task` (`tasks.py:36`).

**Solution:** Build the tool list per session, e.g. `build_tools(settings, guest)`. Include places only when the key is set, and tasks only for signed-in users. Generate the "Tools" part of the prompt from the same list so the prompt never mentions a tool the agent does not have.

### 3.2 Tool results and errors are English text mixed with instructions to the model — P1
Results come in different formats: free text for crop and tasks, JSON for weather and places. Errors are English sentences that mix instructions to the model ("Do not guess…") with wording meant for the user. The model has to translate and filter these on every turn, and some English leaks into the spoken reply.

**Solution:** Use one result format for every tool: `{"ok": bool, "code": "location_not_found" | "unavailable" | "no_match" | ..., "data": {...}, "guidance": "<model-only instruction>"}`. Add one prompt rule: *"Tool results are English data. Explain them in the caller's language. Never read field names, codes, JSON or URLs aloud. Say units as words (degrees Celsius, millimetres of rain)."*

### 3.3 The model has to invent `task_id` and `status` for task requests — P1
`update_farming_task(task_id, title, status)` (`tasks.py:16`): the model must make up an ID and reuse it "for updates", but `status` can only be `requested`, so updates are not really possible. A model that invents a new ID on each call creates duplicate tasks. A model that reuses one ID overwrites an unrelated request. The language of `title` (shown in the UI) is not specified.

**Solution:** Change the tool to `request_farming_call(title: str, contact: str | None)`, generate the ID on the server, and remove `status` until other statuses exist. Specify: *"title: short English summary"* (or the caller's language, but pick one so the UI is consistent). De-duplicate by a normalized title within the same room.

### 3.4 The voice model may run out of tokens before it speaks — P1
`worker.py:105-112` uses `openai/gpt-oss-20b` (a reasoning model) with `max_completion_tokens=512` and no `reasoning_effort`. The default effort can use most of the 512 tokens on reasoning, especially after a large weather JSON result. That gives empty or cut-off replies and slower responses. The phonebook summary call already sets `reasoning_effort` (`phonebook.py:83`); the voice LLM does not.

**Solution:** Pass `reasoning_effort="low"` to `openai.LLM`, and track `reasoning_tokens` against `completion_tokens` in the existing metrics log. Consider `parallel_tool_calls=False` so the model does not run weather and places in the same turn without the caller's input.

### 3.5 The caller hears silence while a tool runs — P2
Weather can take up to 20 s and places up to 12 s. The crop database query has no timeout and depends on the pool's 10 s connect timeout plus query time. Nothing is spoken while these run.

**Solution:** Speak a short acknowledgement in the caller's language before slow tools (e.g. `session.say` from a `RunContext`, or tell the model to say "Let me check" before calling a tool). Wrap the crop query in `asyncio.timeout(8)`.

### 3.6 The weather rule can block plain weather questions — P2
"Establish farming context and location, then use get_weather" can make the model question or refuse "what's the weather in Guntur tomorrow?". Weather is farming-relevant enough by itself.

**Solution:** "For weather, ask only for a missing location, then call get_weather."

---

## 4. Sessions, memory and API

### 4.1 Guest mode is half built — P1
`/conversation/guest-connect` (`conversation.py:26`) is identical to `/connect`: it requires sign-in and onboarding, and `sync_user` never sets `guest`. The `guest` branches in `worker.py:81-96` and `tasks.py:36` can never run.

**Solution:** Either finish guest mode (an unauthenticated, rate-limited endpoint that sets `guest: True`) or remove the endpoint, the frontend proxy entry and the dead branches.

### 4.2 Phonebook descriptions can end up in mixed languages — P2
`generate_description` (`phonebook.py:62`) summarizes multilingual statements without saying which language to write in. The description is shown in the UI and added to every prompt, so it may drift between Hindi, Telugu and English across calls.

**Solution:** Add "Write the description in English" (or in the user's preferred language, chosen once) to the summary prompt.

### 4.3 Speech endpoints are public — P1
`/api/v1/speech/synthesize` and `/api/v1/speech/transcribe` have no `CurrentUser` dependency. The frontend does not proxy them, but anyone who can reach the backend can spend Gnani credits (up to 5000 characters or 8 MB per request).

**Solution:** Add `user: CurrentUser` to both routes, or remove them if only LiveKit is used. Add basic per-user rate limiting.

### 4.4 Shutdown can create a database pool just to close it — P2
`app/main.py:14` calls `get_pool()` in `finally`. When the API never used the database, this creates a pool at shutdown. When `DATABASE_URL` is unset, it raises during shutdown.

**Solution:** Track whether the pool was created (e.g. `get_pool.cache_info().currsize`) and only close it in that case.

### 4.5 Secrets in the working tree — P2 (not committed)
`backend/opencall.json` (Firebase service-account private key) and `backend/.env` are git-ignored and not tracked, which is correct. Keep it that way. Rotate the key if it was ever shared, and prefer `FIREBASE_SERVICE_ACCOUNT_JSON` from a secret store in deployments.

---

## 5. Missing tests (the current suite does not cover these)
- Language-override false positives (Tamil Nadu, bengal gram, Punjab) and a preference that persists across turns.
- TTS language for each pair of script and session language.
- Tool docstrings require English arguments, and the native-script retry path.
- Crop search returns rows for multi-word natural questions and for crop synonyms.
- Tool list depends on configuration (no Geoapify key, guest caller).

---

## TODO

### P0: multilingual correctness
- [x] Tighten `requested_language`: require verb + language name together, exclude place and crop names, add regression tests (2.1)
- [x] Keep an explicit language preference across turns in `TurnLanguage` (2.2)
- [x] Fix TTS script routing: add Devanagari, apply to all sessions, remove the dead `mr-IN` branch (2.3)
- [ ] Tool docstrings: require English/Latin-script arguments with the state; add a native-script retry hint (1.1)
- [ ] Rewrite crop search: OR-based ranking, crop synonyms, English keyword arguments (1.3)

### P1: reliable tool use and security
- [ ] Default geocoding to India (`countryCode=IN`, `countrycode:in`) and return the state (1.2)
- [ ] Use `indic-auto` STT for all sessions with `preferred_language` (2.4)
- [ ] Restructure the system prompt into labelled sections with one language section (2.5)
- [ ] Build the tool list per session from config and guest state; generate the tool prompt from it (3.1)
- [ ] One result and error format for all tools, plus the "explain in the caller's language, no JSON/URLs" rule (3.2)
- [ ] Replace `update_farming_task` with `request_farming_call(title, contact?)` and a server-generated ID (3.3)
- [ ] Set `reasoning_effort="low"` on the voice LLM and decide on `parallel_tool_calls` (3.4)
- [ ] Add `source_name` to crop knowledge and stop reading URLs aloud (1.4)
- [ ] Make the dosage rule explicit (1.5)
- [ ] Finish or remove guest mode (4.1)
- [x] Require auth on `/speech/*` and add a per-user, per-process rate limit (4.3). A shared limiter is still needed to enforce a global limit across replicas.

### P2: cleanup and polish
- [ ] Speak a localized acknowledgement during slow tools; add a timeout to the crop DB query (3.5)
- [ ] Simplify the weather rule (3.6)
- [ ] Use `preferred_language` or remove it (2.6)
- [ ] One shared definition of supported languages (2.7)
- [ ] Fix the summary language for phonebook descriptions (4.2)
- [ ] Close the DB pool only if it was created (4.4)
- [ ] Decide between embeddings and full-text search for crop knowledge; drop whichever is unused (1.3)
- [ ] Add the missing tests listed in section 5
