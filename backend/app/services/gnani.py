"""Lazy Gnani REST clients; constructing a client does not make API calls."""

from functools import lru_cache
from typing import TYPE_CHECKING

import requests
from pydantic import SecretStr

from app.core.config import get_settings

if TYPE_CHECKING:
    from gnani.stt import GnaniSTTClient


class GnaniTTSV3Client:
    """Use the documented REST API; SDK 0.8.1 rejects v3 voices/language."""

    def __init__(self, api_key: str):
        self._api_key = SecretStr(api_key)

    def synthesize(self, text: str, *, voice: str, language: str, request_id: str) -> bytes:
        response = requests.post(
            "https://api.vachana.ai/api/v1/tts/inference",
            headers={
                "X-API-Key-ID": self._api_key.get_secret_value(),
                "X-API-Request-ID": request_id,
                "Content-Type": "application/json",
            },
            json={
                "text": text, "model": "timbre-v3.0", "voice": voice,
                "language": language,
                "audio_config": {
                    "sample_rate": 48000, "encoding": "linear_pcm",
                    "container": "wav", "num_channels": 1, "sample_width": 2,
                },
            },
            timeout=(10, 60),
        )
        response.raise_for_status()
        return response.content


def _get_api_key() -> str:
    key = get_settings().gnani_api_key
    if key is None or not key.get_secret_value().strip():
        raise RuntimeError("Set GNANI_API_KEY in backend/.env to use Gnani.")
    return key.get_secret_value()


@lru_cache
def get_gnani_stt_client() -> "GnaniSTTClient":
    api_key = _get_api_key()
    from gnani.stt import GnaniSTTClient

    return GnaniSTTClient(api_key=api_key)


@lru_cache
def get_gnani_tts_client() -> GnaniTTSV3Client:
    return GnaniTTSV3Client(api_key=_get_api_key())
