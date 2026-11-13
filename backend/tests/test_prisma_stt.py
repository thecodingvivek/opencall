import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.prisma_stt import PrismaSTT
from livekit.agents import APIStatusError


class PrismaSTTTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_sends_prisma_model_and_existing_language(self):
        client = PrismaSTT(api_key='test-key', language='indic-auto', sample_rate=16000)
        stream = client.stream()
        ws = MagicMock()
        ws.recv = AsyncMock(return_value=json.dumps({'type': 'connected'}))
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=ws)
        connection.__aexit__ = AsyncMock(return_value=False)
        with patch('app.services.prisma_stt.websockets.connect', return_value=connection) as connect, \
             patch.object(stream, '_send_audio', new=AsyncMock()), \
             patch.object(stream, '_recv_messages', new=AsyncMock()):
            await stream._run()
        self.assertEqual(client.model, 'prisma-v3.0')
        self.assertEqual(connect.call_args.kwargs['additional_headers'], {
            'x-api-key-id': 'test-key', 'language_code': 'indic-auto',
            'x-sample-rate': '16000', 'model': 'prisma-v3.0',
        })
        await stream.aclose()

    async def test_initial_provider_error_is_not_silently_ignored(self):
        client = PrismaSTT(api_key='test-key', language='te-IN')
        stream = client.stream()
        ws = MagicMock()
        ws.recv = AsyncMock(return_value=json.dumps({'type': 'error', 'message': 'invalid model'}))
        connection = MagicMock()
        connection.__aenter__ = AsyncMock(return_value=ws)
        connection.__aexit__ = AsyncMock(return_value=False)
        with patch('app.services.prisma_stt.websockets.connect', return_value=connection):
            with self.assertRaises(APIStatusError):
                await stream._run()
        await stream.aclose()
