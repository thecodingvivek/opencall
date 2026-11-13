import asyncio
import threading
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from livekit.agents import ToolError
from tools.crop_knowledge import search_crop_knowledge


class CropKnowledgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_wait_does_not_block_event_loop(self):
        loop = asyncio.get_running_loop()
        started = asyncio.Event()
        release = threading.Event()
        row = {'crop': 'rice', 'problem': 'blight', 'symptoms': 'spots', 'cause': 'fungus',
               'fertilizer': '', 'treatment': '', 'dosage': '', 'safety_note': '',
               'region': ['India'], 'source_url': 'https://example.org'}
        conn = MagicMock()
        def execute(*args):
            loop.call_soon_threadsafe(started.set)
            if not release.wait(timeout=3):
                raise TimeoutError('event loop did not release the database query')
            return MagicMock(fetchall=lambda: [row])
        conn.execute.side_effect = execute
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = conn
        with patch('tools.crop_knowledge._embed', return_value=[0.1]), \
             patch('tools.crop_knowledge.get_pool', return_value=pool), \
             patch('tools.crop_knowledge.send_step', new=AsyncMock()) as step:
            task = asyncio.create_task(search_crop_knowledge(' leaf spots ', ' rice ', ' India '))
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                self.assertFalse(task.done())
            finally:
                release.set()
            result = await task
        self.assertIn('Source: https://example.org', result)
        self.assertEqual(conn.execute.call_args.args[1], ([0.1], 'rice', 'India'))
        step.assert_any_await('crop_search_completed', {'matches': 1})

    async def test_database_failure_remains_a_safe_tool_error(self):
        with patch('tools.crop_knowledge._embed', return_value=[0.1]), \
             patch('tools.crop_knowledge.get_pool', side_effect=RuntimeError('private details')), \
             patch('tools.crop_knowledge.send_step', new=AsyncMock()) as step:
            with self.assertRaises(ToolError) as error:
                await search_crop_knowledge('leaf spots')
        self.assertNotIn('private details', str(error.exception))
        step.assert_awaited_with('crop_search_failed', {})
