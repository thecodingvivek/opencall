import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from livekit.agents import APIConnectOptions, APIConnectionError, APITimeoutError
from websockets.protocol import State
from app.services.realtime_speech import ConversationTTS


def message(audio=b"", final=False):
    return json.dumps({"type": "complete" if final else "audio", "data": {
        "audio": base64.b64encode(audio).decode(), "is_final": final}})


class Socket:
    def __init__(self, messages, observer=None):
        self.messages = iter(messages)
        self.observer = observer
        self.state = State.OPEN
        self.sent = []
        self.close = AsyncMock()

    async def send(self, message): self.sent.append(json.loads(message))
    def __aiter__(self): return self
    async def __anext__(self):
        if self.observer:
            self.observer()
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration


class StartupBufferTests(unittest.IsolatedAsyncioTestCase):
    async def test_output_language_follows_hindi_or_english_text(self):
        provider = ConversationTTS(api_key="test", voice="Shivani", language="hi-IN")
        hindi = provider.synthesize("नमस्ते किसान")
        self.assertEqual(hindi._language, "hi-IN")
        english = provider.synthesize("Hello farmer")
        self.assertEqual(english._language, "en-IN")
        await hindi.aclose()
        await english.aclose()

    async def test_indic_script_selects_synthesis_language(self):
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        for text, language in [("వందనం రైతు", "te-IN"), ("வணக்கம்", "ta-IN"), ("નમસ્તે", "gu-IN")]:
            stream = provider.synthesize(text)
            self.assertEqual(stream._language, language)
            await stream.aclose()

    async def run_stream(self, messages, observer=None):
        emitter = Mock()
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        stream = provider.synthesize("Hello", conn_options=APIConnectOptions(max_retry=0))
        with patch("app.services.realtime_speech.websockets.connect", new=AsyncMock(return_value=Socket(messages, observer))):
            await stream._run(emitter)
        await stream.aclose()
        await provider.aclose()
        return emitter

    async def test_buffers_until_threshold_then_streams(self):
        pushes = []
        emitter = Mock()
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        stream = provider.synthesize("Hello", conn_options=APIConnectOptions(max_retry=0))
        socket = Socket([message(b"a" * 9601), message(b"b" * 9599), message(b"c" * 20), message(final=True)],
                        lambda: pushes.append(emitter.push.call_count))
        with patch("app.services.realtime_speech.websockets.connect", new=AsyncMock(return_value=socket)):
            await stream._run(emitter)
        self.assertEqual(pushes, [0, 0, 1, 2])
        self.assertEqual(b"".join(call.args[0] for call in emitter.push.call_args_list), b"a" * 9601 + b"b" * 9599 + b"c" * 20)
        emitter.flush.assert_called_once()
        await stream.aclose()
        await provider.aclose()

    async def test_short_complete_stream_is_released(self):
        emitter = await self.run_stream([message(b"\0\0" * 100), message(final=True)])
        self.assertEqual(emitter.push.call_args.args[0], b"\0\0" * 100)
        emitter.flush.assert_called_once()

    async def test_incomplete_short_stream_is_rejected(self):
        with self.assertRaises(APIConnectionError):
            await self.run_stream([message(b"\0\0" * 100)])

    async def test_network_failure_is_reported_as_connection_error(self):
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        stream = provider.synthesize("Hello", conn_options=APIConnectOptions(max_retry=0))
        with patch("app.services.realtime_speech.websockets.connect", side_effect=OSError("network unavailable")):
            with self.assertRaises(APIConnectionError):
                await stream._run(Mock())
        await stream.aclose()


class ConnectionReuseTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_socket_and_closes_at_end_of_call(self):
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        socket = Socket([message(b"aa"), message(final=True), message(b"bb"), message(final=True)])
        with patch("app.services.realtime_speech.websockets.connect", new=AsyncMock(return_value=socket)) as connect:
            first, second = provider.synthesize("First"), provider.synthesize("Second")
            await first._run(Mock())
            await second._run(Mock())
            self.assertEqual(connect.await_count, 1)
            self.assertEqual([item["text"] for item in socket.sent], ["First", "Second"])
            await first.aclose()
            await second.aclose()
            await provider.aclose()
            socket.close.assert_awaited_once()

    async def test_interruption_discards_socket_and_next_request_reconnects(self):
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        waiting = asyncio.Event()
        class BlockingSocket(Socket):
            async def __anext__(self):
                waiting.set()
                await asyncio.Event().wait()
        first_socket = BlockingSocket([])
        second_socket = Socket([message(b"ok"), message(final=True)])
        with patch("app.services.realtime_speech.websockets.connect", new=AsyncMock(side_effect=[first_socket, second_socket])) as connect:
            first = provider.synthesize("Interrupted")
            await waiting.wait()
            await first.aclose()
            first_socket.close.assert_awaited_once()
            second = provider.synthesize("Next")
            await second._run(Mock())
            self.assertEqual(connect.await_count, 2)
            await first.aclose()
            await second.aclose()
            await provider.aclose()

    async def test_closed_idle_socket_is_replaced(self):
        provider = ConversationTTS(api_key="test", voice="Shivani", language="en-IN")
        first_socket = Socket([message(b"aa"), message(final=True)])
        second_socket = Socket([message(b"bb"), message(final=True)])
        with patch("app.services.realtime_speech.websockets.connect", new=AsyncMock(side_effect=[first_socket, second_socket])) as connect:
            first, second = provider.synthesize("First"), provider.synthesize("Second")
            await first._run(Mock())
            first_socket.state = State.CLOSED
            await second._run(Mock())
            self.assertEqual(connect.await_count, 2)
            await first.aclose()
            await second.aclose()
            await provider.aclose()


class StreamingTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_active_stream_can_last_longer_than_timeout(self):
        class SlowSocket(Socket):
            async def __anext__(self):
                await asyncio.sleep(.04)
                return await super().__anext__()
        socket = SlowSocket([message(b'aa'), message(b'bb'), message(b'cc'), message(final=True)])
        provider = ConversationTTS(api_key='test', voice='Shivani', language='en-IN')
        with patch('app.services.realtime_speech.websockets.connect', new=AsyncMock(return_value=socket)):
            async with provider.synthesize('A long response', conn_options=APIConnectOptions(max_retry=0, timeout=.1)) as stream:
                result = await stream.collect()
            self.assertEqual(bytes(result.data)[:6], b'aabbcc')
            await provider.aclose()

    async def test_stalled_stream_times_out_and_closes_socket(self):
        class StalledSocket(Socket):
            async def __anext__(self):
                await asyncio.sleep(1)
        socket = StalledSocket([])
        provider = ConversationTTS(api_key='test', voice='Shivani', language='en-IN')
        with patch('app.services.realtime_speech.websockets.connect', new=AsyncMock(return_value=socket)):
            async with provider.synthesize('A response', conn_options=APIConnectOptions(max_retry=0, timeout=.05)) as stream:
                with self.assertRaises(APITimeoutError):
                    await stream.collect()
            socket.close.assert_awaited_once()
            await provider.aclose()
