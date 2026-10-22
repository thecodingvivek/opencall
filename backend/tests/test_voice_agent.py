import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pydantic import SecretStr
from app import voice_agent


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_connects_before_room_io_and_enables_interruptions(self):
        callbacks = []
        connected = False
        ctx = Mock()
        ctx.job.metadata = json.dumps({'language_code': 'te-IN', 'voice': 'Lakshmi',
                                      'participant_identity': 'user-test'})
        ctx.add_shutdown_callback.side_effect = callbacks.append

        async def connect():
            nonlocal connected
            connected = True

        ctx.connect = AsyncMock(side_effect=connect)
        ctx.wait_for_participant = AsyncMock()
        session = Mock()
        session.aclose = AsyncMock()
        session.on.side_effect = lambda event: lambda handler: handler

        async def start(**kwargs):
            self.assertTrue(connected, 'RoomIO requires an already connected room')
            self.assertEqual(kwargs['room_options'].participant_identity, 'user-test')

        session.start = AsyncMock(side_effect=start)
        settings = Mock(gnani_api_key=SecretStr('test-gnani'),
                        groq_api_key=SecretStr('test-groq'), groq_model='openai/gpt-oss-20b',
                        conversation_max_seconds=1800)
        with patch.object(voice_agent, 'settings', settings), \
             patch.object(voice_agent, 'AgentSession', return_value=session) as factory, \
             patch.object(voice_agent.silero.VAD, 'load', return_value=Mock()):
            await voice_agent.conversation(ctx)
        config = factory.call_args.kwargs
        self.assertTrue(config['stt'].capabilities.streaming)
        self.assertEqual(config['tts'].model, 'timbre-v3.0')
        self.assertTrue(config['turn_handling']['interruption']['enabled'])
        self.assertEqual(config['turn_handling']['interruption']['min_duration'], .35)
        ctx.wait_for_participant.assert_awaited_once_with(identity='user-test')
        session.generate_reply.assert_called_once()
        for callback in callbacks:
            await callback()
        await config['llm'].aclose()
