from types import SimpleNamespace
import unittest
from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from observability import tracing


class ObservabilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.exporter = InMemorySpanExporter()
        self.provider = TracerProvider()
        self.provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        self.provider.add_span_processor(tracing.SessionAttributes())
        self.addCleanup(self.provider.shutdown)
        for patcher in [patch.object(tracing, '_provider', self.provider),
                        patch.object(tracing, 'configure', return_value=self.provider),
                        patch.object(tracing, 'get_observability_settings',
                                     return_value=SimpleNamespace(capture_content=False))]:
            patcher.start()
            self.addCleanup(patcher.stop)

    async def test_session_and_description_share_trace_and_metadata_without_content(self):
        @tracing.observed('phonebook.generate_description', kind='LLM')
        async def generate(description, statements):
            tracing.record_llm_usage({'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}})
            return 'A teacher.'
        observation = tracing.SessionObservation('demo', 'test-room', 'en-IN', 'Shivani')
        with observation.activate():
            await generate('private existing description', 'private user speech')
        await observation.finish()
        spans = {span.name: span for span in self.exporter.get_finished_spans()}
        parent, child = spans['opencall.session'], spans['phonebook.generate_description']
        self.assertEqual(child.parent.span_id, parent.context.span_id)
        self.assertEqual(child.attributes['session.id'], 'test-room')
        self.assertEqual(child.attributes['user.id'], 'demo')
        self.assertEqual(child.attributes['llm.token_count.total'], 30)
        self.assertEqual(child.attributes['openinference.span.kind'], 'LLM')
        self.assertNotIn('input.value', child.attributes)
        self.assertNotIn('output.value', child.attributes)

    async def test_handled_failure_has_error_status_without_exception_content(self):
        @tracing.observed('phonebook.update_description')
        async def fail():
            try:
                raise ValueError('private provider payload')
            except ValueError as error:
                tracing.record_outcome('failed', error)
        await fail()
        span = self.exporter.get_finished_spans()[0]
        self.assertEqual(span.status.status_code.name, 'ERROR')
        self.assertEqual(span.attributes['error.type'], 'ValueError')
        self.assertNotIn('private provider payload', str(span.attributes) + str(span.events))

    async def test_content_capture_is_explicit(self):
        @tracing.observed('description', kind='LLM')
        async def generate(statement):
            return 'A teacher.'
        with patch.object(tracing, 'get_observability_settings',
                          return_value=SimpleNamespace(capture_content=True)):
            await generate('I teach science.')
        span = self.exporter.get_finished_spans()[0]
        self.assertIn('I teach science.', span.attributes['input.value'])
        self.assertEqual(span.attributes['output.value'], 'A teacher.')

    async def test_weather_execution_has_a_tool_span_without_input_content(self):
        from unittest.mock import AsyncMock
        from tools.weather import get_weather
        with patch('tools.weather.weather_data', new=AsyncMock(return_value={'source': 'Open-Meteo'})):
            await get_weather(location='Hyderabad', start='tomorrow')
        span = self.exporter.get_finished_spans()[0]
        self.assertEqual(span.name, 'tool.get_weather')
        self.assertEqual(span.attributes['openinference.span.kind'], 'TOOL')
        self.assertEqual(span.attributes['tool.name'], 'get_weather')
        self.assertNotIn('input.value', span.attributes)
