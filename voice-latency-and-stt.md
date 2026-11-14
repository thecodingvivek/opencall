# Voice latency and STT quality plan

This plan covers the continuous call path in `voiceagent/worker.py`:
browser → LiveKit → Gnani STT → Groq LLM → Gnani Timbre v3 TTS → browser.
It lists what currently adds delay or hurts recognition, and what to change, in
priority order. Each item points at the code it affects.

Reviewed against the code on November 13, 2026, with `livekit-agents==1.8.8`,
`livekit-plugins-gnani==1.8.8`, and the
[Gnani streaming STT docs](https://docs.gnani.ai/api/STT/stt-websocket).
The timings below are estimates from configuration and provider docs. None of
them has been measured on a real call yet, so step 0 comes first.

**Implementation update:** The continuous call worker now requests Prisma v3.0 explicitly
and reuses its TTS WebSocket across completed sentences. Interrupted or failed
requests discard the socket; the next request reconnects. The 400 ms startup
buffer remains in place. The first request still opens the connection on demand.
The crop database lookup also runs in a worker thread, leaving the event loop
free while it waits for the database. The embedding model has since been removed;
crop guidance now uses PostgreSQL text search. Prisma's per-transcript detected language
is now passed to the turn prompt and used as a TTS language hint. Explicit
language requests are recognized by a best-effort phrase matcher.
The measurements and other recommendations below remain a historical plan and have
not yet been verified in a real call.

## 0. Measure before tuning

The worker logs no per-turn timings today. The Phoenix integration described
in `architecture.md` is no longer in the repository (`backend/observability/`
does not exist), so there is nothing to check a change against.

LiveKit 1.8.8 already computes the numbers that matter. Log them per turn:

```python
from livekit.agents import metrics

@session.on("metrics_collected")
def on_metrics(event):
    m = event.metrics
    if isinstance(m, metrics.EOUMetrics):
        log.info("eou_delay=%.3f transcription_delay=%.3f", m.end_of_utterance_delay, m.transcription_delay)
    elif isinstance(m, metrics.LLMMetrics):
        log.info("llm_ttft=%.3f tokens=%s", m.ttft, m.completion_tokens)
    elif isinstance(m, metrics.TTSMetrics):
        log.info("tts_ttfb=%.3f", m.ttfb)
```

Track one headline number: **time from the user stopping speaking to the first
assistant audio**, which is roughly `eou_delay + llm_ttft + tts_ttfb`. Record the
median and p90 across 20 or more real turns in Hindi, English, and one other
language. Do not log transcript text at info level.

## 1. Where the time goes today

| Stage | Current setting | Estimated cost | Source |
| --- | --- | --- | --- |
| Gnani server end-of-speech | `x-min-silence-ms` not sent, so the default is 500 ms (kept on purpose, see 2.2) | 500 ms | Gnani docs |
| Gnani transcription | Prisma v2.5 (no `model` header is sent) | ~300–400 ms (docs examples show 320–380 ms) | Gnani docs |
| LiveKit endpointing | Silero `min_silence_duration=0.35`, `min_delay=0.5` | Runs in parallel; turn waits for the final transcript | `worker.py` |
| Groq first token | `gpt-oss-20b` with no `reasoning_effort`, so Groq's default (`medium`) applies | Reasoning tokens are generated before any spoken text | `worker.py`, plugin `llm.py` |
| First sentence | LiveKit sentence adapter waits for a full sentence | Depends on sentence length | `realtime_speech.py` |
| TTS connection | Reuses `wss://api.vachana.ai/api/v1/tts` across completed sentences | First request and reconnects pay the connection cost | `realtime_speech.py` |
| TTS startup buffer | `STARTUP_BUFFER_MS = 400` (added in `ee71b71` to stop choppy playback) | Up to 400 ms held back per sentence | `realtime_speech.py` |

Gnani STT emits only final transcripts (`interim_results=False` in the plugin),
so the turn cannot complete until Gnani's own 500 ms silence timer expires and
transcription finishes. That wait is kept on purpose (2.2), so the savings have
to come from the stages after it: the LLM, sentence buffering, and TTS
connections.

## 2. Latency changes, highest value first

### 2.1 Set `reasoning_effort="low"` on the voice LLM

`openai.LLM` only sets a reasoning default for OpenAI's own GPT-5 models
(`_supports_reasoning_effort` in `livekit/plugins/openai/models.py`), so
`openai/gpt-oss-20b` runs at Groq's default of `medium`. The live voice path does not set this option. The phonebook summary now uses a
separate configurable model.

```python
openai.LLM(..., model=settings.groq_model, reasoning_effort="low")
```

Groq accepts only `low`, `medium`, or `high` for gpt-oss; `minimal` and `none`
return HTTP 400. Check that tool-call accuracy (weather, crop search, task
creation) holds at `low` with a handful of scripted prompts.

Also consider lowering `max_completion_tokens` from 512. Replies are meant to be
one to three sentences, and reasoning tokens count toward this limit.

### 2.2 Keep Gnani's 500 ms silence window; do not shorten it

The 500 ms default is deliberate. `x-min-silence-ms` controls how long Gnani
waits after the **caller** stops before it closes their utterance. It does not
change how TTS audio is generated. It still affects how the assistant sounds,
indirectly:

1. With a shorter window, a natural pause ("mere khet mein... gehu hai") closes
   the utterance early and Gnani sends half a sentence.
2. LiveKit treats that fragment as a complete turn and the assistant starts
   replying.
3. The caller keeps talking, which interrupts the assistant, so its audio stops
   after a word or two and a new reply starts.

The caller hears this as the voice cutting in and out. Lowering the value saves
a few hundred milliseconds per turn but makes these false turns more likely,
so it is not worth it here. If pauses still split turns, try raising it to
600–700 ms rather than lowering it.

For the same reason, do **not** send Gnani's `commit` frame whenever Silero
detects silence. Silero's `min_silence_duration` is 0.35 s, which is shorter
than 500 ms, so committing on it would cause the splitting described above.

Ways to cut latency without shortening the silence window:

- The LLM change in 2.1, the TTS connection change in 2.3, and the prewarming
  in 2.4 all remove delay *after* the turn ends, so they do not risk splitting
  turns.
- If a semantic end-of-turn model is added later, sending `commit` only when
  that model is confident the caller has finished is safe. That is a separate
  change, and it needs testing with Hindi and Hinglish speech.

### 2.3 Reuse the TTS connection; keep the startup buffer (implemented)

Before this change, `_AudioStream._run` opened and closed a WebSocket for every sentence. On a
three-sentence reply that is three handshakes to `api.vachana.ai`. The first
one delays the start of the reply. The later ones can leave a silent gap
between sentences if the previous sentence finishes playing before the next
one's audio arrives. That gap is another source of choppy-sounding speech.

- Reuse one socket per call, with one request at a time. Gnani documents sending
  another request after completion. The socket opens on demand and is closed
  on call shutdown, interruption, or failure.
- Consider prewarming the connection at call start to reduce first-sentence latency.
- Keep `STARTUP_BUFFER_MS = 400`. It was added in commit `ee71b71` to stop
  choppy playback when Gnani's first chunks arrive unevenly. Only revisit it
  after connection reuse is in place, and lower it in small steps (300, then
  250) while listening on a real call. Go back up at the first sign of
  stutter, because smooth audio matters more here than 100 ms.

### 2.4 Prewarm per-process resources

`silero.VAD.load()` runs inside every job. The Postgres pool uses `min_size=0`,
so the first query in a process also pays a TLS connect to Supabase. The crop
embedding model has been removed, so there is no embedding model to prewarm.

Use the worker's setup hook (`AgentServer.setup_fnc`) to load these once per
process:

```python
def prewarm(proc):
    proc.userdata["vad"] = silero.VAD.load(min_silence_duration=0.35)
    get_pool()                   # consider min_size=1 for the worker

server.setup_fnc = prewarm
# in conversation(): vad=ctx.proc.userdata["vad"]
```

### 2.5 Stop blocking the event loop in tools (crop query implemented)

Previously, `search_crop_knowledge` ran a synchronous psycopg query directly inside an
`async` function:

```python
with get_pool().connection() as conn:
    rows = conn.execute(...).fetchall()
```

The query now runs through `asyncio.to_thread`, including connection checkout
and fetching rows. The event loop can continue handling audio while the tool
waits for the result. Real-call impact remains unmeasured.

Smaller tool items:

- `send_step(...)` is awaited before tool work starts. Make it fire-and-forget
  (`asyncio.create_task`) so a reliable data publish never delays the tool.
- `tools/weather.py` creates a new `aiohttp.ClientSession` per call, which
  means a new TLS handshake each time. A module-level session reused across
  calls is cheaper.
- Have the agent say a short filler line ("Let me check the forecast") before
  slow tools, so the caller hears something while the tool runs.

### 2.6 Make the greeting cheaper (implemented for calls without a description)

Bilingual calls without a saved phonebook description use a fixed Hindi greeting
through `session.say`, avoiding an LLM request. Calls with a description and
non-bilingual calls continue to use `session.generate_reply`. TTS is still used.

### 2.7 Preemptive TTS

Preemptive LLM generation is already on by default in 1.8.8
(`PreemptiveGenerationOptions.enabled=True`). TTS still waits for the turn to be
confirmed. Try:

```python
turn_handling={..., "preemptive_generation": {"preemptive_tts": True}}
```

This trades some wasted Gnani TTS requests for earlier audio. Measure both.

### 2.8 Region

The worker runs in LiveKit Cloud `ap-south` (Mumbai) and Gnani is India-hosted,
which is a good fit. Groq's serving regions are outside India, so each LLM call
crosses a long network path. Measure `llm_ttft` from the deployed worker, not
from a laptop, before comparing models or providers.

## 3. STT quality

### 3.1 Upgrade to Prisma v3.0

The plugin sends no `model` header, so streaming STT uses **Prisma v2.5**.
Prisma v3.0 (`model: prisma-v3.0`) adds most of the features below. A custom
`SpeechStream` subclass in `backend/app/services/` (the same pattern as
`ConversationTTS`) can send the extra headers.

### 3.2 Fix the Hindi/English language setting

`worker.py` sends `language="indic-auto"` for `hi-IN` and `en-IN` callers. That
asks Gnani to choose among all supported Indic languages, although only Hindi
and English are expected. A wider search space gives the model more ways to
pick the wrong language on short or accented utterances. On Prisma v3.0, send
the candidate list instead (Gnani describes it as a hint, not a lock):

```text
language_code: hi-IN,en-IN
```

The plugin's own `GnaniSTTLanguages` type also lists `"en-IN,hi-IN"` as the
auto-detection value.

### 3.3 Use the detected language instead of guessing from script (implemented)

Prisma v3.0's `detected_language_code` is passed through `SpeechData.language`.
The worker applies the final transcript's language to the next reply prompt and
TTS, provided it matches the completed turn. A recognized explicit request to
reply in a named language takes precedence. TTS still uses native script as a
signal when it differs from the hint; absent or unsupported detection falls
back to the previous behavior.

Gnani says the detection is derived from the transcript's script, and the
explicit-request matcher recognizes common phrases rather than every possible
wording. Mixed and romanized speech therefore need real-call evaluation.

### 3.4 Add farming vocabulary with `keyterms`

Prisma v3.0 accepts up to 200 `keyterms` per connection. Crop, pest, and input
names are exactly where general STT models fail. Seed the list from
`backend/data/crop_knowledge_seed.json` plus common terms, for example:

- inputs: urea, DAP, MOP, potash, NPK, zinc sulphate, neem oil
- crops in local names: dhaan, gehu, kapas, mirchi, tamatar
- pests and diseases: tana chhedak (stem borer), jhulsa (blight), safed makkhi (whitefly)
- institutions: KVK, Krishi Vigyan Kendra

Write non-ASCII terms as `\u`-escaped JSON, as the Gnani docs describe, because
some WebSocket clients refuse non-ASCII header values. Also send
`topic: "Indian farming: crops, soil, pests, fertilizer, weather"`.

On Prisma v2.5, the equivalent is `bias_list` plus `bias_score`, limited to 100
single words.

### 3.5 Choose the output format deliberately

Farmers often mix English product names into Hindi or Telugu speech. The
`codemix` format (Prisma v3.0) keeps English words in Latin script, so "DAP"
reaches the LLM and the crop search as `DAP` rather than a Devanagari spelling.
Text search and tool arguments may benefit. Compare `verbatim` and
`codemix` on the same recordings before switching.

### 3.6 Tune Gnani VAD for a browser microphone

Send VAD headers explicitly instead of relying on defaults:

| Header | Suggested start | Why |
| --- | --- | --- |
| `x-vad-threshold` | 0.55–0.65 | Default 0.7 is tuned for noisy telephony; laptop mics need lower |
| `x-min-speech-ms` | 100 (default) | Keep short answers like "haan" |
| `x-min-segment-ms` | 120 (default) | Raising this drops one-word replies |
| `x-idle-timeout-sec` | 300 or more | Default 60 s closes the STT stream if the caller goes quiet |

### 3.7 Session limits that can end a call

- Gnani caps a streaming STT session at **15 minutes**, but
  `CONVERSATION_MAX_SECONDS` is 1,800 (30 minutes).
- Gnani closes the stream after **60 s** without speech by default.

The plugin uses `max_retry=0`, and the worker's `on_error` handler shuts the
whole session down on any non-recoverable error. Test a call with 70 seconds
of silence and a call longer than 15 minutes. If either ends the call, reconnect
the STT stream proactively (for example at 14 minutes) or lower the conversation
limit to 15 minutes.

### 3.8 Audio capture

- `TryCall.tsx` enables browser `noiseSuppression`, `echoCancellation`, and
  `autoGainControl`. Echo cancellation is needed for barge-in. Browser noise
  suppression can remove consonants that STT depends on; A/B test with it off.
- The worker receives 16 kHz mono, which matches Gnani's native rate. Keep it.
- If the worker stays on LiveKit Cloud, test LiveKit's server-side noise
  cancellation plugin against browser suppression.

### 3.9 Build a small evaluation set

Record 30–50 short consented clips: Hindi, English, Hinglish, and two other
supported languages, with crop and fertilizer names, numbers, and a noisy
outdoor sample. Store reference transcripts and compute word error rate for each
config change (model, `keyterms`, `format`, VAD). Without this, STT changes are
judged by impression. Keep recordings out of Git and out of the build context.

## 4. Prompt and context hygiene

- The shortened `FARMING_INSTRUCTIONS` prompt (about 1,800 characters) is stable at the start of each
  request, which suits Groq's prefix caching for gpt-oss. A synthetic `Hello`
  request with the same three tool schemas measured 1,079 prompt tokens before
  shortening and 709 after; actual call usage varies with context and caching.
  Keep dynamic content (UTC time, caller profile) at the end, as it is now.
- `on_user_turn_completed` adds a short language instruction on each turn,
  including the selected language when available and respecting explicit requests.
- `architecture.md` still describes TinyDB and Phoenix. Update it when these
  changes land so the docs match the code.

## 5. Suggested order

| Step | Change | Effort | Expected effect |
| --- | --- | --- | --- |
| 1 | Log turn metrics (section 0) | Small | Baseline for all later steps |
| 2 | `reasoning_effort="low"` (2.1) | One line | Lower LLM first-token time |
| 3 | Move crop DB query off the event loop (2.5, implemented) | Small | Avoid event-loop stalls from the crop DB query |
| 4 | Prewarm VAD and DB pool (2.4) | Small | Reduce per-call setup and first-query delays |
| 5 | Custom Gnani STT stream: Prisma v3.0, `hi-IN,en-IN`, `keyterms`, idle timeout; keep 500 ms silence (2.2, 3.1–3.4, 3.6) | Medium | Better recognition without splitting turns |
| 6 | TTS connection reuse; keep the 400 ms startup buffer (2.3, implemented) | Medium | Fewer connection handshakes and potential gaps between sentences |
| 7 | Detected language drives TTS and reply language (3.3, implemented) | Medium | Language hints for replies and TTS; real-call evaluation needed |
| 8 | STT evaluation set (3.9), then `codemix` and audio capture A/B tests (3.5, 3.8) | Medium | Measured STT improvements |
| 9 | Fixed greeting, preemptive TTS, filler lines (2.6, 2.7, 2.5) | Small | Shorter perceived waits |

After each step, run the backend tests from `backend/` with
`.venv-voice/bin/python -m unittest discover -s tests -v` (`test_voice_agent.py`
checks the current worker settings) and compare the step 0 metrics against the
baseline.
