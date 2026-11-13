"""Gnani WebSocket audio output, wrapped in LiveKit sentence streaming."""
import asyncio
import base64
import json

import websockets
from websockets.protocol import State
from livekit.agents import (
    APIConnectionError, APIConnectOptions, APIStatusError, APITimeoutError,
    DEFAULT_API_CONNECT_OPTIONS, tts, utils,
)

# 400 ms of mono 16-bit PCM at 24 kHz. Buffer each synthesis stream before
# releasing its first frames; once started, continue streaming immediately.
STARTUP_BUFFER_MS = 400

SCRIPT_LANGUAGES = (
    ("\u0980", "\u09ff", "bn-IN"), ("\u0a00", "\u0a7f", "pa-IN"),
    ("\u0a80", "\u0aff", "gu-IN"), ("\u0b80", "\u0bff", "ta-IN"),
    ("\u0c00", "\u0c7f", "te-IN"), ("\u0c80", "\u0cff", "kn-IN"),
    ("\u0d00", "\u0d7f", "ml-IN"),
)


class ConversationTTS(tts.TTS):
    def __init__(self, *, api_key: str, voice: str, language: str):
        # AgentSession wraps non-text-streaming providers in its sentence adapter.
        # Each sentence emits PCM as it arrives, before the LLM response completes.
        super().__init__(capabilities=tts.TTSCapabilities(streaming=False),
                         sample_rate=24000, num_channels=1)
        self._key = api_key
        self._voice = voice
        self._language = language
        self._socket = None
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def model(self) -> str:
        return "timbre-v3.0"

    @property
    def provider(self) -> str:
        return "Gnani"

    def synthesize(self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS):
        language = self._language
        for start, end, script_language in SCRIPT_LANGUAGES:
            if any(start <= char <= end for char in text):
                language = script_language
                break
        else:
            if language in {"hi-IN", "en-IN"}:
                language = "hi-IN" if any("\u0900" <= char <= "\u097f" for char in text) else "en-IN"
        return _AudioStream(provider=self, input_text=text, conn_options=conn_options, language=language)

    async def _connect(self):
        if self._closed:
            raise APIConnectionError("Gnani TTS provider is closed")
        if self._socket is not None and self._socket.state is not State.OPEN:
            await self._discard_socket()
        if self._socket is None:
            self._socket = await websockets.connect(
                "wss://api.vachana.ai/api/v1/tts",
                additional_headers={"X-API-Key-ID": self._key},
                open_timeout=10, close_timeout=3,
            )
        return self._socket

    async def _discard_socket(self):
        socket, self._socket = self._socket, None
        if socket is not None:
            await socket.close()

    async def aclose(self):
        self._closed = True
        async with self._lock:
            await self._discard_socket()


class _AudioStream(tts.ChunkedStream):
    def __init__(self, *, provider: ConversationTTS, input_text: str, conn_options: APIConnectOptions, language: str):
        super().__init__(tts=provider, input_text=input_text, conn_options=conn_options)
        self._provider = provider
        self._language = language

    async def _run(self, output_emitter: tts.AudioEmitter):
        provider = self._provider
        output_emitter.initialize(request_id=utils.shortuuid(), sample_rate=provider.sample_rate,
                                  num_channels=1, mime_type="audio/pcm", frame_size_ms=20)
        pending = b""
        started = False
        startup_bytes = provider.sample_rate * 2 * STARTUP_BUFFER_MS // 1000
        complete = False
        saw_start = False
        try:
            async with asyncio.timeout(self._conn_options.timeout):
                async with provider._lock:
                    try:
                        ws = await provider._connect()
                        await ws.send(json.dumps({
                            "text": self._input_text, "voice": provider._voice,
                            "model": provider.model, "language": self._language,
                            "audio_config": {
                                "sample_rate": provider.sample_rate, "encoding": "linear_pcm",
                                "container": "raw", "num_channels": 1, "sample_width": 2,
                            },
                        }))
                        async for message in ws:
                            if isinstance(message, bytes):
                                audio = message
                                final = False
                            else:
                                data = json.loads(message)
                                if data.get("type") == "error":
                                    raise APIStatusError("Gnani speech stream failed", status_code=502)
                                if data.get("type") == "start":
                                    saw_start = True
                                    continue
                                # Gnani can send a second, request-level completion after
                                # the final audio event. It belongs to the preceding
                                # request if it arrives before this request's start.
                                if (data.get("type") == "complete" and data.get("request_id")
                                        and not saw_start):
                                    continue
                                body = data.get("data") or {}
                                audio = base64.b64decode(body.get("audio", ""), validate=True)
                                final = data.get("type") == "complete" or body.get("is_final", False)
                            pending += audio
                            count = len(pending) - len(pending) % 2
                            if count and (started or count >= startup_bytes or final):
                                output_emitter.push(pending[:count])
                                pending = pending[count:]
                                started = True
                            if final:
                                complete = True
                                break
                        if not complete or pending:
                            raise APIConnectionError("Gnani speech stream ended before completion")
                    except BaseException:
                        await provider._discard_socket()
                        raise
            output_emitter.flush()
        except TimeoutError as error:
            raise APITimeoutError("Gnani speech stream timed out") from error
        except (websockets.WebSocketException, OSError, ValueError) as error:
            raise APIConnectionError("Gnani speech stream failed") from error
