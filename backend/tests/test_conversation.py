import base64
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

import jwt
from fastapi.testclient import TestClient
from livekit.agents import APIConnectOptions
from pydantic import SecretStr

from app.main import app
from app.api.routes.auth import require_user
from app.services.realtime_speech import ConversationTTS


class TokenTests(unittest.TestCase):
    def setUp(self):
        app.dependency_overrides[require_user] = lambda: {"username": "demo", "onboarded": True}
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.settings = Mock(gnani_api_key=SecretStr('gnani-private'),
            groq_api_key=SecretStr('groq-private'), livekit_api_key='test-key',
            livekit_api_secret=SecretStr('s' * 40), livekit_url='ws://127.0.0.1:7880')
        patcher = patch('app.services.conversation.get_settings', return_value=self.settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        readiness = patch('app.api.routes.conversation.ensure_voice_available', new=AsyncMock())
        readiness.start()
        self.addCleanup(readiness.stop)

    def test_restricted_token_and_agent_dispatch(self):
        response = self.client.post('/api/v1/conversation/connect', json={
            'language_code': 'te-IN', 'voice': 'Lakshmi'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        details = response.json()
        claims = jwt.decode(details['participant_token'], 's' * 40, algorithms=['HS256'])
        self.assertEqual(claims['sub'], details['participant_identity'])
        self.assertEqual(claims['video']['room'], details['room_name'])
        self.assertEqual(claims['video']['canPublishSources'], ['microphone'])
        self.assertNotIn('roomAdmin', claims['video'])
        self.assertEqual(claims['exp'] - claims['nbf'], 600)
        dispatch = claims['roomConfig']['agents'][0]
        self.assertEqual(dispatch['agentName'], 'opencall-conversation')
        metadata = json.loads(dispatch['metadata'])
        self.assertEqual(metadata['language_code'], 'te-IN')
        self.assertEqual(metadata['voice'], 'Lakshmi')
        self.assertEqual(metadata['participant_identity'], details['participant_identity'])
        self.assertEqual(metadata['username'], 'demo')
        self.assertNotIn('call_id', details)
        self.assertNotIn('private', response.text)
        other = self.client.post('/api/v1/conversation/connect', json={}).json()
        self.assertNotEqual(details['room_name'], other['room_name'])

    def test_account_is_derived_from_session_and_required(self):
        response = self.client.post('/api/v1/conversation/connect', json={
            'username': 'someone-else', 'user_id': 'forged'})
        self.assertEqual(response.status_code, 200)
        claims = jwt.decode(response.json()['participant_token'], 's' * 40, algorithms=['HS256'])
        metadata = json.loads(claims['roomConfig']['agents'][0]['metadata'])
        self.assertEqual(metadata['username'], 'demo')
        app.dependency_overrides.pop(require_user)
        self.assertEqual(self.client.post('/api/v1/conversation/connect', json={}).status_code, 401)
        self.assertEqual(self.client.get('/api/v1/conversation/phonebook').status_code, 401)

    def test_invalid_options(self):
        for payload in [{'voice': 'Pranav'}, {'language_code': 'bad'}]:
            self.assertEqual(self.client.post('/api/v1/conversation/connect', json=payload).status_code, 422)

    def test_missing_credentials(self):
        self.settings.groq_api_key = None
        response = self.client.post('/api/v1/conversation/connect', json={})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('gnani-private', response.text)

    def test_unavailable_voice_service_returns_503_instead_of_join_token(self):
        with patch('app.api.routes.conversation.ensure_voice_available',
                   new=AsyncMock(side_effect=RuntimeError('Voice service is unavailable'))):
            response = self.client.post('/api/v1/conversation/connect', json={})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('participant_token', response.json())


class Socket:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []
        self.closed = False
    async def send(self, data): self.sent.append(json.loads(data))
    def __aiter__(self): return self
    async def __anext__(self):
        try: return next(self.messages)
        except StopIteration: raise StopAsyncIteration
    async def close(self): self.closed = True


def message(data, final=False):
    return json.dumps({'type': 'complete' if final else 'audio',
        'data': {'audio': base64.b64encode(data).decode(), 'is_final': final}})


class StreamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_aligns_pcm_and_preserves_v3_settings(self):
        pcm = b'\x01\x00' * 2400
        socket = Socket([message(pcm[:101]), message(pcm[101:]), message(b'', True)])
        provider = ConversationTTS(api_key='test-key', voice='Lakshmi', language='te-IN')
        with patch('app.services.realtime_speech.websockets.connect', new=AsyncMock(return_value=socket)):
            async with provider.synthesize('Hello', conn_options=APIConnectOptions(max_retry=0)) as stream:
                result = await stream.collect()
        self.assertFalse(socket.closed)
        await provider.aclose()
        self.assertTrue(socket.closed)
        self.assertEqual(bytes(result.data)[:len(pcm)], pcm)
        # LiveKit may append a short silence frame to mark the final segment.
        tail = bytes(result.data)[len(pcm):]
        self.assertLessEqual(len(tail), 960)
        self.assertTrue(all(value == 0 for value in tail))
        self.assertEqual(result.sample_rate, 24000)
        self.assertEqual(socket.sent[0]['model'], 'timbre-v3.0')
        self.assertEqual(socket.sent[0]['language'], 'te-IN')
        self.assertEqual(socket.sent[0]['audio_config']['container'], 'raw')

    async def test_incomplete_stream_is_rejected(self):
        socket = Socket([message(b'\0\0' * 1200)])
        provider = ConversationTTS(api_key='test-key', voice='Shivani', language='en-IN')
        with patch('app.services.realtime_speech.websockets.connect', new=AsyncMock(return_value=socket)):
            async with provider.synthesize('Hello', conn_options=APIConnectOptions(max_retry=0)) as stream:
                with self.assertRaises(Exception): await stream.collect()
        self.assertTrue(socket.closed)
