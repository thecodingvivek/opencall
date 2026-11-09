import unittest
from unittest.mock import AsyncMock, patch

from livekit.agents import ToolError
from tools.tasks import update_farming_task


class FarmingTaskTests(unittest.IsolatedAsyncioTestCase):
    async def test_publishes_blocked_outbound_call(self):
        with patch('tools.tasks.send_step', new=AsyncMock(return_value=True)) as send:
            result = await update_farming_task('fertilizer-1', ' Call shop to check  fertilizer stock ', 'blocked')
        send.assert_awaited_once_with('farming_task', {
            'id': 'fertilizer-1', 'title': 'Call shop to check fertilizer stock', 'status': 'blocked'})
        self.assertIn('no call will be made', result)

    async def test_rejects_invalid_fields_and_failed_delivery(self):
        with patch('tools.tasks.send_step', new=AsyncMock(return_value=False)) as send:
            for task_id, title, status in [('bad id', 'Test', 'blocked'), ('valid', '', 'blocked'),
                                            ('valid', 'x' * 101, 'blocked'), ('valid', 'Test', 'unknown'),
                                            ('valid', 'Call a shop', 'completed'), ('valid', 'Call a shop', 'in_progress')]:
                with self.assertRaises(ToolError):
                    await update_farming_task(task_id, title, status)
            send.assert_not_awaited()
            with self.assertRaises(ToolError):
                await update_farming_task('valid', 'Call a shop', 'blocked')
