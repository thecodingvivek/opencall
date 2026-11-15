import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from app.services.phonebook import PhonebookEntry
from livekit.agents.llm import ChatContext
from livekit.agents.llm.tool_context import ToolContext

from pydantic import SecretStr
from voiceagent import worker as voice_agent


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_and_personalized_greetings(self):
        session = Mock()
        voice_agent.start_greeting(session, bilingual=True, description='')
        session.say.assert_called_once()
        session.generate_reply.assert_not_called()
        session.reset_mock()
        voice_agent.start_greeting(session, bilingual=True, description='A rice farmer')
        session.generate_reply.assert_called_once()
        session.say.assert_not_called()
        session.reset_mock()
        voice_agent.start_greeting(session, bilingual=False, description='')
        session.generate_reply.assert_called_once()

    async def test_turn_context_requests_caller_language(self):
        agent = voice_agent.FarmingAgent(instructions="Help farmers")
        context = ChatContext()
        context.add_message(role="user", content="नमस्ते")
        await agent.on_user_turn_completed(context, context.items[-1])
        self.assertIn("language of the caller's latest utterance", context.items[-1].text_content)

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
            self.assertEqual(len(kwargs['agent'].tools), 4)
            self.assertIn('use get_weather', kwargs['agent'].instructions)
            self.assertIn('refuse unrelated requests', kwargs['agent'].instructions)
            self.assertIn('search_farming_places', kwargs['agent'].instructions)

        session.start = AsyncMock(side_effect=start)
        settings = Mock(gnani_api_key=SecretStr('test-gnani'),
                        groq_api_key=SecretStr('test-groq'), groq_model='openai/gpt-oss-20b',
                        groq_fallback_model='openai/gpt-oss-120b', conversation_max_seconds=1800)
        with patch.object(voice_agent, 'settings', settings), \
             patch.object(voice_agent, 'AgentSession', return_value=session) as factory, \
             patch.object(voice_agent, 'get_phonebook_store', return_value=store), \
             patch.object(voice_agent, 'update_description_after_session', new=AsyncMock()) as update, \
             patch.object(voice_agent.silero.VAD, 'load', return_value=Mock()):
            await voice_agent.conversation(ctx)
            store.get.assert_called_once_with('demo')
            usage = voice_agent.metrics.LLMMetrics.model_construct(
                prompt_tokens=100, completion_tokens=20, total_tokens=120,
                prompt_cached_tokens=10, reasoning_tokens=3)
            with self.assertLogs('voiceagent.worker', level='INFO') as captured:
                handlers['metrics_collected'](Mock(metrics=usage))
            self.assertIn('task=voice', captured.output[0])
            self.assertIn('total_tokens=120', captured.output[0])
            self.assertNotIn('I teach science', captured.output[0])
            self.assertNotIn('conversation_item_added', handlers)
            handlers['close'](Mock())
            ctx.shutdown.assert_called_once_with(reason='conversation ended')
            for callback in callbacks:
                await callback()
            update.assert_awaited_once_with(store, 'demo', ['I teach science.', 'I prefer short replies.'])
        config = factory.call_args.kwargs
        self.assertIsInstance(config['llm'], voice_agent.FallbackAdapter)
        self.assertEqual([instance.model for instance in config['llm']._llm_instances],
                         ['openai/gpt-oss-20b', 'openai/gpt-oss-120b'])
        primary_llm = config['llm']._llm_instances[0]
        schema = ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=primary_llm._strict_tool_schema)[0]
        self.assertEqual(schema['function']['parameters']['required'], ['location'])
        task_schema = ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=primary_llm._strict_tool_schema)[1]
        self.assertEqual(task_schema['function']['name'], 'update_farming_task')
        self.assertEqual(set(task_schema['function']['parameters']['required']), {'task_id', 'title', 'status'})
        self.assertEqual(ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=primary_llm._strict_tool_schema)[2]['function']['name'], 'search_crop_knowledge')
        places_schema = ToolContext(voice_agent.AGENT_TOOLS).parse_function_tools(
            'openai', strict=primary_llm._strict_tool_schema)[3]
        self.assertEqual(places_schema['function']['name'], 'search_farming_places')
        self.assertEqual(set(places_schema['function']['parameters']['required']), {'location', 'kind'})
        self.assertTrue(config['stt'].capabilities.streaming)
        self.assertEqual(config['stt'].model, 'prisma-v3.0')
        self.assertEqual(config['tts'].model, 'timbre-v3.0')
        self.assertTrue(config['turn_handling']['interruption']['enabled'])
        self.assertEqual(config['turn_handling']['interruption']['min_duration'], .35)
        ctx.wait_for_participant.assert_awaited_once_with(identity='user-test')
        session.generate_reply.assert_called_once()
        await config['llm'].aclose()


class FallbackTests(unittest.IsolatedAsyncioTestCase):
    async def run_call(self, *, max_seconds=1000, fallback_model='openai/gpt-oss-120b'):
        """Start a mocked call and return its handlers, session, context and shutdown callbacks."""
        callbacks = []
        ctx = Mock()
        ctx.job.metadata = json.dumps({'language_code': 'te-IN', 'voice': 'Lakshmi',
                                      'participant_identity': 'user-test', 'username': 'demo'})
        ctx.add_shutdown_callback.side_effect = callbacks.append
        ctx.connect = AsyncMock()
        ctx.wait_for_participant = AsyncMock()
        ctx.room.local_participant.publish_data = AsyncMock()
        session = Mock()
        session.history = ChatContext()
        session.start = AsyncMock()
        session.aclose = AsyncMock()
        session.interrupt = AsyncMock()
        session.say.return_value = Mock(wait_for_playout=AsyncMock())
        handlers = {}
        session.on.side_effect = lambda event: lambda handler: handlers.setdefault(event, handler)
        store = Mock()
        store.get.return_value = PhonebookEntry(username='demo')
        settings = Mock(gnani_api_key=SecretStr('test-gnani'), groq_api_key=SecretStr('test-groq'),
                        groq_model='openai/gpt-oss-20b', groq_fallback_model=fallback_model,
                        conversation_max_seconds=max_seconds)
        patches = [patch.object(voice_agent, 'settings', settings),
                   patch.object(voice_agent, 'AgentSession', return_value=session),
                   patch.object(voice_agent, 'get_phonebook_store', return_value=store),
                   patch.object(voice_agent, 'update_description_after_session', new=AsyncMock()),
                   patch.object(voice_agent.silero.VAD, 'load', return_value=Mock())]
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        await voice_agent.conversation(ctx)
        self.addAsyncCleanup(self.run_callbacks, callbacks)
        return handlers, session, ctx

    async def run_callbacks(self, callbacks):
        for callback in callbacks:
            await callback()

    @staticmethod
    def spoken(session):
        return [call.args[0] for call in session.say.call_args_list]

    @staticmethod
    def statuses(ctx):
        return [json.loads(call.args[0]) for call in ctx.room.local_participant.publish_data.call_args_list
                if call.kwargs.get('topic') == voice_agent.CALL_STATUS_TOPIC]

    @staticmethod
    def error(kind, recoverable=False):
        return Mock(error=Mock(recoverable=recoverable, type=kind, error=RuntimeError('provider down')))

    async def settle(self):
        for _ in range(5):
            await voice_agent.asyncio.sleep(0)

    async def test_failed_reply_asks_to_repeat_then_ends_politely(self):
        handlers, session, ctx = await self.run_call()
        handlers['error'](self.error('llm_error', recoverable=True))
        await self.settle()
        session.say.assert_not_called()
        handlers['error'](self.error('llm_error'))
        await self.settle()
        self.assertEqual(self.spoken(session), [voice_agent.call_message('repeat', 'te-IN')])
        ctx.shutdown.assert_not_called()
        handlers['error'](self.error('llm_error'))
        await self.settle()
        self.assertEqual(self.spoken(session)[-1], voice_agent.call_message('trouble', 'te-IN'))
        self.assertEqual(self.statuses(ctx), [{'type': 'call_ending', 'reason': 'provider_error'}])
        session.shutdown.assert_called_once()
        ctx.shutdown.assert_called_once_with(reason='conversation provider error')

    async def test_successful_reply_resets_failure_count(self):
        handlers, session, ctx = await self.run_call()
        handlers['error'](self.error('llm_error'))
        await self.settle()
        usage = voice_agent.metrics.LLMMetrics.model_construct(
            prompt_tokens=1, completion_tokens=1, total_tokens=2, prompt_cached_tokens=0,
            reasoning_tokens=0, metadata=None)
        handlers['metrics_collected'](Mock(metrics=usage))
        handlers['error'](self.error('llm_error'))
        await self.settle()
        self.assertEqual(self.spoken(session), [voice_agent.call_message('repeat', 'te-IN')] * 2)
        ctx.shutdown.assert_not_called()

    async def test_broken_speech_output_only_informs_the_screen(self):
        handlers, session, ctx = await self.run_call()
        handlers['error'](self.error('tts_error'))
        await self.settle()
        session.say.assert_not_called()
        self.assertEqual(self.statuses(ctx), [{'type': 'call_ending', 'reason': 'provider_error'}])
        ctx.shutdown.assert_called_once()

    async def test_time_limit_warns_then_says_goodbye(self):
        with patch.object(voice_agent, 'TIME_WARNING_SECONDS', 0.05):
            handlers, session, ctx = await self.run_call(max_seconds=0.15)
            await voice_agent.asyncio.sleep(0.3)
        self.assertEqual(self.spoken(session), [voice_agent.call_message('time_warning', 'te-IN'),
                                                voice_agent.call_message('time_goodbye', 'te-IN')])
        self.assertEqual(self.statuses(ctx), [{'type': 'time_warning', 'seconds_left': 0.05},
                                              {'type': 'call_ending', 'reason': 'time_limit'}])
        session.interrupt.assert_awaited_once_with(force=True)
        ctx.shutdown.assert_called_once_with(reason='conversation time limit')

    async def test_backup_model_can_be_disabled(self):
        await self.run_call(fallback_model='')
        config = voice_agent.AgentSession.call_args.kwargs
        self.assertNotIsInstance(config['llm'], voice_agent.FallbackAdapter)
        self.assertEqual(config['llm'].model, 'openai/gpt-oss-20b')
