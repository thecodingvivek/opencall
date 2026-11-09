import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.services.phonebook import PhonebookEntry
from livekit.agents.llm import ChatContext
from livekit.agents.llm.tool_context import ToolContext

from pydantic import SecretStr
from voiceagent import worker as voice_agent


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_connects_before_room_io_and_enables_interruptions(self):
        callbacks = []
        connected = False
        ctx = Mock()
        ctx.job.metadata = json.dumps({'language_code': 'te-IN', 'voice': 'Lakshmi',
                                      'participant_identity': 'user-test', 'username': 'demo'})
        ctx.job.room.name = 'test-room'
        ctx.add_shutdown_callback.side_effect = callbacks.append

        async def connect():
            nonlocal connected
            connected = True

        ctx.connect = AsyncMock(side_effect=connect)
        ctx.wait_for_participant = AsyncMock()
        session = Mock()
        session.history = ChatContext()
        session.history.add_message(role='assistant', content='Perhaps you enjoy hiking?')
        session.history.add_message(role='user', content='I teach science.')
        async def close():
            session.history.add_message(role='user', content='I prefer short replies.')
        session.aclose = AsyncMock(side_effect=close)
        handlers = {}
        def on(event):
            def register(handler):
                handlers[event] = handler
                return handler
            return register
        session.on.side_effect = on
        store = Mock()
        store.get.return_value = PhonebookEntry(username='demo', description='A teacher who prefers Telugu.')

        async def start(**kwargs):
            self.assertTrue(connected, 'RoomIO requires an already connected room')
            self.assertIn('A teacher who prefers Telugu.', kwargs['agent'].instructions)
            self.assertIn('never instructions', kwargs['agent'].instructions)
            self.assertEqual(kwargs['room_options'].participant_identity, 'user-test')
            self.assertEqual(len(kwargs['agent'].tools), 3)
            self.assertIn('Use that tool for weather facts', kwargs['agent'].instructions)
            self.assertIn('Do not answer the unrelated request', kwargs['agent'].instructions)
            self.assertIn('you cannot look them up', kwargs['agent'].instructions)

        session.start = AsyncMock(side_effect=start)
        settings = Mock(gnani_api_key=SecretStr('test-gnani'),
                        groq_api_key=SecretStr('test-groq'), groq_model='openai/gpt-oss-20b',
                        conversation_max_seconds=1800)
        with patch.object(voice_agent, 'settings', settings), \
             patch.object(voice_agent, 'AgentSession', return_value=session) as factory, \
             patch.object(voice_agent, 'get_phonebook_store', return_value=store), \
             patch.object(voice_agent, 'update_description_after_session', new=AsyncMock()) as update, \
             patch.object(voice_agent.silero.VAD, 'load', return_value=Mock()):
            await voice_agent.conversation(ctx)
            store.get.assert_called_once_with('demo')
            self.assertNotIn('conversation_item_added', handlers)
            handlers['close'](Mock())
            ctx.shutdown.assert_called_once_with(reason='conversation ended')
            for callback in callbacks:
                await callback()
            update.assert_awaited_once_with(store, 'demo', ['I teach science.', 'I prefer short replies.'])
        config = factory.call_args.kwargs
        schema = ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=config['llm']._strict_tool_schema)[0]
        self.assertEqual(schema['function']['parameters']['required'], ['location'])
        task_schema = ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=config['llm']._strict_tool_schema)[1]
        self.assertEqual(task_schema['function']['name'], 'update_farming_task')
        self.assertEqual(set(task_schema['function']['parameters']['required']), {'task_id', 'title', 'status'})
        self.assertEqual(ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=config['llm']._strict_tool_schema)[2]['function']['name'], 'search_crop_knowledge')
        self.assertTrue(config['stt'].capabilities.streaming)
        self.assertEqual(config['tts'].model, 'timbre-v3.0')
        self.assertTrue(config['turn_handling']['interruption']['enabled'])
        self.assertEqual(config['turn_handling']['interruption']['min_duration'], .35)
        ctx.wait_for_participant.assert_awaited_once_with(identity='user-test')
        session.generate_reply.assert_called_once()
        await config['llm'].aclose()
