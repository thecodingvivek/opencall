"""Lazy Gnani REST clients; constructing a client does not make API calls."""

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from gnani.stt import GnaniSTTClient
    from gnani.tts import GnaniTTSClient


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
def get_gnani_tts_client() -> "GnaniTTSClient":
    api_key = _get_api_key()
    from gnani.tts import GnaniTTSClient

    return GnaniTTSClient(api_key=api_key)
