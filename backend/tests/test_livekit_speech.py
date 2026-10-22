"""Real LiveKit audio handling with mocked provider HTTP responses."""
import asyncio
import io
import unittest
import wave
from unittest.mock import AsyncMock, Mock, patch

from pydantic import SecretStr

from app.services.gnani import (
    get_gnani_stt_client, get_gnani_tts_client, recognize, synthesize_audio,
)
from app.services.livekit_gnani import DashboardSTT, DashboardTTS


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b'\x01\x00' * 4410)
    return output.getvalue()


def session_for(status=200, audio=None):
    response = Mock(status=status)
    response.read = AsyncMock(return_value=wav_bytes() if audio is None else audio)
    response.json = AsyncMock(return_value={'transcript': 'నమస్కారం'})
    response.text = AsyncMock(return_value='private upstream details')
    context = Mock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = Mock(closed=False)
    session.post.return_value = context
    session.close = AsyncMock()
    return session


class LiveKitTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_stt_frame_and_session_cleanup(self):
        client = DashboardSTT(api_key='test-key', language='te-IN')
        session = session_for()
        with patch('app.services.livekit_gnani.aiohttp.ClientSession', return_value=session):
            self.assertEqual(await recognize(client, b'\0\0' * 16000), 'నమస్కారం')
        session.close.assert_awaited_once()
        kwargs = session.post.call_args.kwargs
        self.assertEqual(kwargs['url'], 'https://api.vachana.ai/stt/v3')
        self.assertEqual(kwargs['headers']['X-API-Key-ID'], 'test-key')
        fields = kwargs['data']._fields
        self.assertEqual(next(v for info, _, v in fields if info['name'] == 'language_code'), 'te-IN')
        data = next(v for info, _, v in fields if info['name'] == 'audio_file')
        with wave.open(io.BytesIO(data)) as wav:
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getnframes(), 16000)

    async def test_v3_stream_payload_and_decoded_audio(self):
        client = DashboardTTS(api_key='test-key', voice='Lakshmi', language='te-IN')
        session = session_for()
        with patch('app.services.livekit_gnani.aiohttp.ClientSession', return_value=session):
            audio = await synthesize_audio(client, '<excited> Hello')
        session.close.assert_awaited_once()
        payload = session.post.call_args.kwargs['json']
        self.assertEqual(payload['model'], 'timbre-v3.0')
        self.assertEqual(payload['language'], 'te-IN')
        self.assertEqual(payload['voice'], 'Lakshmi')
        self.assertEqual(payload['text'], '<excited> Hello')
        self.assertEqual(payload['audio_config']['sample_rate'], 44100)
        with wave.open(io.BytesIO(audio)) as wav:
            self.assertEqual(wav.getframerate(), 44100)
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.readframes(wav.getnframes()), b'\x01\x00' * 4410)

    async def test_tts_errors_close_session_without_retry(self):
        for status, data in [(403, None), (200, b'not audio')]:
            client = DashboardTTS(api_key='test-key', voice='Shivani', language='en-IN')
            session = session_for(status, data)
            with patch('app.services.livekit_gnani.aiohttp.ClientSession', return_value=session):
                with self.assertRaises(Exception):
                    await synthesize_audio(client, 'Hello')
            session.close.assert_awaited_once()
            session.post.assert_called_once()

    async def test_stt_error_closes_session_without_retry(self):
        client = DashboardSTT(api_key='test-key', language='en-IN')
        session = session_for(403)
        with patch('app.services.livekit_gnani.aiohttp.ClientSession', return_value=session):
            with self.assertRaises(Exception):
                await recognize(client, b'\0\0' * 16000)
        session.close.assert_awaited_once()
        session.post.assert_called_once()

    async def test_cancellation_closes_session(self):
        client = DashboardSTT(api_key='test-key', language='en-IN')
        session = session_for()
        entered = asyncio.Event()

        async def wait_for_cancel():
            entered.set()
            await asyncio.Future()

        session.post.return_value.__aenter__.side_effect = wait_for_cancel
        with patch('app.services.livekit_gnani.aiohttp.ClientSession', return_value=session):
            task = asyncio.create_task(recognize(client, b'\0\0' * 16000))
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        session.close.assert_awaited_once()

    async def test_concurrent_requests_keep_voice_and_language(self):
        clients = [DashboardTTS(api_key='test-key', voice='Shivani', language='hi-IN'),
                   DashboardTTS(api_key='test-key', voice='Avinash', language='te-IN')]
        sessions = [session_for(), session_for()]
        with patch('app.services.livekit_gnani.aiohttp.ClientSession', side_effect=sessions):
            await asyncio.gather(*(synthesize_audio(c, 'Hello') for c in clients))
        payloads = [s.post.call_args.kwargs['json'] for s in sessions]
        self.assertEqual({(p['voice'], p['language']) for p in payloads},
                         {('Shivani', 'hi-IN'), ('Avinash', 'te-IN')})
        for session in sessions:
            session.close.assert_awaited_once()


class ProviderConfigurationTests(unittest.TestCase):
    def test_missing_or_empty_key_rejected_without_network(self):
        for key in (None, SecretStr('  ')):
            with patch('app.services.gnani.get_settings', return_value=Mock(gnani_api_key=key)):
                with self.assertRaises(RuntimeError):
                    get_gnani_stt_client(language='en-IN')
                with self.assertRaises(RuntimeError):
                    get_gnani_tts_client(voice='Shivani', language='en-IN')

    def test_factory_passes_backend_key_without_opening_http(self):
        with patch('app.services.gnani.get_settings',
                   return_value=Mock(gnani_api_key=SecretStr('test-key'))), \
             patch('app.services.livekit_gnani.aiohttp.ClientSession') as session:
            stt = get_gnani_stt_client(language='te-IN')
            tts = get_gnani_tts_client(voice='Lakshmi', language='te-IN')
        self.assertIsInstance(stt, DashboardSTT)
        self.assertIsInstance(tts, DashboardTTS)
        self.assertEqual(tts.model, 'timbre-v3.0')
        session.assert_not_called()
