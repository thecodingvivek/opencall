import base64
import json
import unittest
from unittest.mock import Mock, patch

from livekit.agents import APIConnectOptions, APIConnectionError
from app.services.realtime_speech import ConversationTTS


def message(audio=b"", final=False):
    return json.dumps({"type": "complete" if final else "audio", "data": {
        "audio": base64.b64encode(audio).decode(), "is_final": final}})


class Socket:
    def __init__(self, messages, observer=None):
        self.messages = iter(messages)
        self.observer = observer

    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def send(self, message): pass
    def __aiter__(self): return self
    async def __anext__(self):
        if self.observer:
            self.observer()
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


class StartupBufferTests(unittest.IsolatedAsyncioTestCase):
    async def run_stream(self, messages, observer=None):
        emitter = Mock()
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        stream = provider.synthesize("Hello", conn_options=APIConnectOptions(max_retry=0))
        with patch("app.services.realtime_speech.websockets.connect", return_value=Socket(messages, observer)):
            await stream._run(emitter)
        await stream.aclose()
        return emitter

    async def test_buffers_until_threshold_then_streams(self):
        pushes = []
        emitter = Mock()
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        stream = provider.synthesize("Hello", conn_options=APIConnectOptions(max_retry=0))
        socket = Socket([message(b"a" * 9601), message(b"b" * 9599), message(b"c" * 20), message(final=True)],
                        lambda: pushes.append(emitter.push.call_count))
        with patch("app.services.realtime_speech.websockets.connect", return_value=socket):
            await stream._run(emitter)
        self.assertEqual(pushes, [0, 0, 1, 2])
        self.assertEqual(b"".join(call.args[0] for call in emitter.push.call_args_list), b"a" * 9601 + b"b" * 9599 + b"c" * 20)
        emitter.flush.assert_called_once()
        await stream.aclose()

    async def test_short_complete_stream_is_released(self):
        emitter = await self.run_stream([message(b"\0\0" * 100), message(final=True)])
        self.assertEqual(emitter.push.call_args.args[0], b"\0\0" * 100)
        emitter.flush.assert_called_once()

    async def test_incomplete_short_stream_is_rejected(self):
        with self.assertRaises(APIConnectionError):
            await self.run_stream([message(b"\0\0" * 100)])
