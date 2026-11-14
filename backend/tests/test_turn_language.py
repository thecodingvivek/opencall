import json
import unittest
from unittest.mock import Mock

from livekit.agents.llm import ChatContext
from app.services.prisma_stt import PrismaSTT
from app.services.realtime_speech import ConversationTTS
from app.services.turn_language import TurnLanguage, requested_language
from voiceagent.worker import FarmingAgent


class Messages:
    def __init__(self, messages):
        self.messages = iter(messages)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return json.dumps(next(self.messages))
        except StopIteration:
            raise StopAsyncIteration


class TurnLanguageTests(unittest.IsolatedAsyncioTestCase):
    async def test_prisma_exposes_detected_language_and_missing_value(self):
        stream = PrismaSTT(api_key='test', language='indic-auto').stream()
        events = Mock()
        stream._event_ch = events
        await stream._recv_messages(Messages([
            {'type': 'transcript', 'text': 'namaste', 'detected_language_code': 'hi-IN'},
            {'type': 'transcript', 'text': 'hello'},
        ]))
        self.assertEqual(events.send_nowait.call_args_list[0].args[0].alternatives[0].language, 'hi-IN')
        self.assertEqual(events.send_nowait.call_args_list[1].args[0].alternatives[0].language, '')
        await stream.aclose()

    async def test_per_turn_hint_tts_and_explicit_language_override(self):
        state = TurnLanguage()
        provider = ConversationTTS(api_key='test', voice='Shivani', language='en-IN')
        agent = FarmingAgent(instructions='Help farmers', language_state=state, speech=provider)
        state.on_transcript(Mock(is_final=True, transcript='mera khet', language='hi-IN'))
        context = ChatContext()
        context.add_message(role='user', content='mera khet')
        await agent.on_user_turn_completed(context, context.items[-1])
        self.assertIn('Use Hindi', context.items[-1].text_content)
        stream = provider.synthesize('mera khet')
        self.assertEqual(stream._language, 'hi-IN')
        await stream.aclose()
        state.on_transcript(Mock(is_final=True, transcript='please reply in English', language='hi-IN'))
        context.add_message(role='user', content='please reply in English')
        await agent.on_user_turn_completed(context, context.items[-1])
        self.assertIn('Use English', context.items[-1].text_content)
        stream = provider.synthesize('Hello farmer')
        self.assertEqual(stream._language, 'en-IN')
        await stream.aclose()
        await provider.aclose()

    async def test_language_mentions_are_not_switch_requests(self):
        for text in ('My farm is in Tamil Nadu', 'tell me about bengali gram pests',
                     'I grow rice in Punjab and speak punjabi sometimes'):
            with self.subTest(text=text):
                self.assertIsNone(requested_language(text))

    async def test_explicit_preference_persists_and_can_be_changed(self):
        state = TurnLanguage()
        self.assertEqual(state.complete_turn('please speak in Telugu'), 'te-IN')
        state.on_transcript(Mock(is_final=True, transcript='hello', language='en-IN'))
        self.assertEqual(state.complete_turn('hello'), 'te-IN')
        self.assertEqual(state.complete_turn('nothing detected'), 'te-IN')
        self.assertEqual(state.complete_turn('please reply in English'), 'en-IN')
        self.assertEqual(state.complete_turn('another turn'), 'en-IN')
        self.assertEqual(requested_language('हिंदी में बोलो'), 'hi-IN')
        self.assertEqual(requested_language('తెలుగు లో మాట్లాడు'), 'te-IN')

    async def test_missing_and_stale_transcripts_do_not_reuse_language(self):
        state = TurnLanguage()
        state.on_transcript(Mock(is_final=True, transcript='old utterance', language='hi-IN'))
        self.assertIsNone(state.complete_turn('new utterance'))
        state.on_transcript(Mock(is_final=True, transcript='unknown', language=''))
        self.assertIsNone(state.complete_turn('unknown'))
