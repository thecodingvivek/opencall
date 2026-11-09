"""Request-scoped LiveKit speech providers for the HTTP speech endpoints.

The published Gnani plugin omits language from v3 TTS requests. Our
compatibility stream supplies that field while retaining LiveKit audio handling.
"""

import asyncio
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from livekit.plugins.gnani import STT, TTS


def _get_api_key() -> str:
    key = get_settings().gnani_api_key
    if key is None or not key.get_secret_value().strip():
        raise RuntimeError("Set GNANI_API_KEY in backend/.env to use Gnani.")
    return key.get_secret_value()


def get_gnani_stt_client(*, language: str) -> "STT":
    from app.services.livekit_gnani import DashboardSTT

    return DashboardSTT(api_key=_get_api_key(), language=language)


def get_gnani_tts_client(*, voice: str, language: str) -> "TTS":
    from app.services.livekit_gnani import DashboardTTS

    return DashboardTTS(api_key=_get_api_key(), voice=voice, language=language)


async def recognize(client: "STT", pcm: bytes) -> str:
    from livekit import rtc
    from livekit.agents import APIConnectOptions

    async with client:
        event = await client.recognize(
            rtc.AudioFrame(data=pcm, sample_rate=16000, num_channels=1,
                           samples_per_channel=len(pcm) // 2),
            conn_options=APIConnectOptions(max_retry=0, timeout=60),
        )
        if not event.alternatives or not isinstance(event.alternatives[0].text, str):
            raise ValueError("Invalid transcription event")
        return event.alternatives[0].text


async def synthesize_audio(client: "TTS", text: str) -> bytes:
    from livekit.agents import APIConnectOptions

    async with client:
        async with client.synthesize(
            text, conn_options=APIConnectOptions(max_retry=0, timeout=60),
        ) as stream:
            # Bound the whole operation as well as the provider HTTP request.
            async with asyncio.timeout(65):
                frame = await stream.collect()
        if frame.samples_per_channel == 0:
            raise ValueError("Empty synthesis")
        return frame.to_wav_bytes()
