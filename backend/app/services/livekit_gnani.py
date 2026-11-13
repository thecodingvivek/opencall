"""LiveKit plugin lifecycle and Timbre v3 compatibility.

Pinned to livekit-plugins-gnani 1.8.9: its TTS payload only includes language for
v2.5. This stream adds v3 language using LiveKit's standard AudioEmitter. Output
is 44.1 kHz, the highest sample rate accepted by the published plugin.
"""

import asyncio

import aiohttp
from livekit.agents import (
    APIConnectionError, APIConnectOptions, APIStatusError, APITimeoutError,
    DEFAULT_API_CONNECT_OPTIONS, tts, utils,
)
from livekit.plugins import gnani


class _HTTPSession:
    """Own a session explicitly because FastAPI has no LiveKit job context."""

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.close()


class DashboardSTT(_HTTPSession, gnani.STT):
    def __init__(self, *, api_key: str, language: str):
        super().__init__(api_key=api_key, language=language, sample_rate=16000,
                         use_streaming=False)


class DashboardTTS(_HTTPSession, gnani.TTS):
    def __init__(self, *, api_key: str, voice: str, language: str):
        super().__init__(api_key=api_key, voice=voice, language=language,
                         model="timbre-v3.0", sample_rate=44100,
                         encoding="linear_pcm", container="wav",
                         num_channels=1, synthesize_method="rest")

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> tts.ChunkedStream:
        return _V3Stream(provider=self, input_text=text, conn_options=conn_options)


class _V3Stream(tts.ChunkedStream):
    def __init__(self, *, provider: DashboardTTS, input_text: str,
                 conn_options: APIConnectOptions):
        super().__init__(tts=provider, input_text=input_text, conn_options=conn_options)
        self._provider = provider

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        provider = self._provider
        try:
            async with provider._ensure_session().post(
                "https://api.vachana.ai/api/v1/tts/inference",
                headers={"X-API-Key-ID": provider._api_key},
                json={
                    "text": self._input_text, "model": provider.model,
                    "voice": provider._opts.voice, "language": provider._opts.language,
                    "audio_config": {
                        "sample_rate": provider.sample_rate, "num_channels": 1,
                        "sample_width": 2, "encoding": "linear_pcm", "container": "wav",
                    },
                },
                timeout=aiohttp.ClientTimeout(total=self._conn_options.timeout),
            ) as response:
                if response.status != 200:
                    # Avoid putting provider error bodies in application logs.
                    raise APIStatusError("Gnani synthesis failed", status_code=response.status)
                audio = await response.read()
                if audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
                    raise APIConnectionError("Invalid Gnani WAV response")
                output_emitter.initialize(
                    request_id=utils.shortuuid(), sample_rate=provider.sample_rate,
                    num_channels=provider.num_channels, mime_type="audio/wav",
                )
                output_emitter.push(audio)
                output_emitter.flush()
        except asyncio.TimeoutError as error:
            raise APITimeoutError("Gnani synthesis timed out") from error
        except aiohttp.ClientError as error:
            raise APIConnectionError("Gnani synthesis connection failed") from error
