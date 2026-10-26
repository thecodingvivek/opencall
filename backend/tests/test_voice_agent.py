import json
import unittest
from unittest.mock import AsyncMock, Mock, patch
from types import SimpleNamespace

from app.services.phonebook import PhonebookEntry

from pydantic import SecretStr
from app import voice_agent


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_connects_before_room_io_and_enables_interruptions(self):
        callbacks = []
        connected = False
        ctx = Mock()
        ctx.job.metadata = json.dumps({'language_code': 'te-IN', 'voice': 'Lakshmi',
                                      'participant_identity': 'user-test', 'call_id': 'call-test'})
        ctx.job.room.name = 'test-room'
        ctx.add_shutdown_callback.side_effect = callbacks.append

        async def connect():
            nonlocal connected
            connected = True

        ctx.connect = AsyncMock(side_effect=connect)
        ctx.wait_for_participant = AsyncMock()
        session = Mock()
        session.aclose = AsyncMock()
        handlers = {}
        def on(event):
            def register(handler):
                handlers[event] = handler
                return handler
            return register
        session.on.side_effect = on
        store = Mock()
        store.activate.return_value = {'user_id': 'account-test'}
        store.get.return_value = PhonebookEntry(user_id='account-test', username='demo',
            description='A teacher who prefers Telugu.', previous_summary='Wants help with a lesson.')

        async def start(**kwargs):
            self.assertTrue(connected, 'RoomIO requires an already connected room')
            self.assertIn('A teacher who prefers Telugu.', kwargs['agent'].instructions)
            self.assertIn('Wants help with a lesson.', kwargs['agent'].instructions)
            self.assertIn('never instructions', kwargs['agent'].instructions)
            self.assertEqual(kwargs['room_options'].participant_identity, 'user-test')

        session.start = AsyncMock(side_effect=start)
        settings = Mock(gnani_api_key=SecretStr('test-gnani'),
                        groq_api_key=SecretStr('test-groq'), groq_model='openai/gpt-oss-20b',
                        conversation_max_seconds=1800)
        with patch.object(voice_agent, 'settings', settings), \
             patch.object(voice_agent, 'AgentSession', return_value=session) as factory, \
             patch.object(voice_agent, 'get_phonebook_store', return_value=store), \
             patch.object(voice_agent, 'retry_pending_memory', new=AsyncMock()) as retry, \
             patch.object(voice_agent, 'save_call_memory', new=AsyncMock()) as save, \
             patch.object(voice_agent.silero.VAD, 'load', return_value=Mock()):
            await voice_agent.conversation(ctx)
            handlers['conversation_item_added'](SimpleNamespace(item=SimpleNamespace(
                id='turn-test', role='user', text_content='Plan my next lesson.')))
            store.append_turn.assert_called_once_with('call-test', 'turn-test', 'user', 'Plan my next lesson.')
            retry.assert_awaited_once_with(store, 'account-test')
            handlers['close'](Mock())
            ctx.shutdown.assert_called_once_with(reason='conversation ended')
            for callback in callbacks:
                await callback()
            save.assert_awaited_once_with(store, 'call-test')
            store.end_call.assert_called_once_with('call-test')
        config = factory.call_args.kwargs
        self.assertTrue(config['stt'].capabilities.streaming)
        self.assertEqual(config['tts'].model, 'timbre-v3.0')
        self.assertTrue(config['turn_handling']['interruption']['enabled'])
        self.assertEqual(config['turn_handling']['interruption']['min_duration'], .35)
        ctx.wait_for_participant.assert_awaited_once_with(identity='user-test')
        session.generate_reply.assert_called_once()
        await config['llm'].aclose()
