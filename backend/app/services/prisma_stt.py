"""Select Prisma v3 for LiveKit's Gnani streaming STT integration."""
import asyncio
import contextlib
import json
from dataclasses import replace

import websockets
from livekit.agents import (
    DEFAULT_API_CONNECT_OPTIONS, APIConnectionError, APIConnectOptions,
    APIStatusError, APITimeoutError, utils,
)
from livekit.agents.types import NOT_GIVEN, NotGivenOr
from livekit.agents.utils.misc import is_given
from livekit.plugins.gnani import STT
from livekit.plugins.gnani.stt import SpeechStream


class PrismaSTT(STT):
    @property
    def model(self) -> str:
        return "prisma-v3.0"

    def stream(self, *, language: NotGivenOr[str] = NOT_GIVEN,
               conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> SpeechStream:
        opts = replace(self._opts)
        if is_given(language):
            opts.language = language
        return PrismaSpeechStream(stt=self, opts=opts,
                                  conn_options=self._single_attempt(conn_options))


class PrismaSpeechStream(SpeechStream):
    async def _run(self) -> None:
        headers = {
            "x-api-key-id": self._opts.api_key,
            "language_code": self._opts.language,
            "x-sample-rate": str(self._opts.sample_rate),
            "model": "prisma-v3.0",
        }
        if self._opts.format != "verbatim":
            headers["format"] = self._opts.format
        if self._opts.preferred_language is not None:
            headers["preferred_language"] = self._opts.preferred_language
        try:
            async with websockets.connect(
                self._build_ws_url(), additional_headers=headers,
                ping_interval=20, ping_timeout=20, close_timeout=10,
            ) as ws:
                connected = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if connected.get("type") == "error":
                    raise APIStatusError(message=f"Gnani STT stream error: {connected.get('message', 'Unknown error')}",
                                         status_code=500, body=connected)
                if connected.get("type") != "connected":
                    raise APIConnectionError("Unexpected first message from Gnani STT")
                send_task = asyncio.create_task(self._send_audio(ws), name="gnani-stt-send")
                recv_task = asyncio.create_task(self._recv_messages(ws), name="gnani-stt-recv")
                try:
                    done, _ = await asyncio.wait([send_task, recv_task], return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        task.result()
                    if send_task.done() and not recv_task.done():
                        with contextlib.suppress(asyncio.TimeoutError):
                            await asyncio.wait_for(asyncio.shield(recv_task), timeout=1.0)
                finally:
                    await utils.aio.gracefully_cancel(send_task, recv_task)
        except websockets.exceptions.ConnectionClosed as exc:
            raise APIConnectionError(f"Gnani STT WebSocket closed unexpectedly: {exc}") from exc
        except asyncio.TimeoutError as exc:
            raise APITimeoutError("Gnani STT WebSocket connection timed out") from exc
        except (APIConnectionError, APIStatusError, APITimeoutError):
            raise
        except Exception as exc:
            raise APIConnectionError(f"Gnani STT WebSocket error: {exc}") from exc
