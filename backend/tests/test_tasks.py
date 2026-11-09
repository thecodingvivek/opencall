import json
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from livekit.agents import ToolError
from app.api.routes.auth import require_user
from app.main import app
from app.services.tasks import list_tasks, save_task
from tools.tasks import update_farming_task


class FarmingTaskTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user_id = str(uuid4())
        self.context = Mock()
        self.context.job.metadata = json.dumps({'username': self.user_id})
        self.context.job.room.name = 'room-1'

    async def test_saves_before_publishing_and_survives_delivery_failure(self):
        task = {'id': str(uuid4()), 'title': 'Call shop to check fertilizer stock', 'status': 'requested'}
        with patch('tools.tasks.get_job_context', return_value=self.context), \
             patch('tools.tasks.save_task', return_value=task) as save, \
             patch('tools.tasks.send_step', new=AsyncMock(return_value=False)) as send:
            result = await update_farming_task('fertilizer-1', ' Call shop to check  fertilizer stock ', 'requested')
        save.assert_called_once_with(self.user_id, 'room-1', 'fertilizer-1', task['title'], 'requested')
        send.assert_awaited_once_with('farming_task', task)
        self.assertIn('saved', result)

    async def test_failure_and_invalid_fields_are_not_reported_as_saved(self):
        with patch('tools.tasks.get_job_context', return_value=self.context), \
             patch('tools.tasks.save_task', side_effect=RuntimeError) as save, \
             patch('tools.tasks.send_step', new=AsyncMock()) as send:
            for task_id, title, status in [('bad id', 'Test', 'requested'), ('valid', '', 'requested'),
                                            ('valid', 'x' * 101, 'requested'), ('valid', 'Test', 'unknown')]:
                with self.assertRaises(ToolError):
                    await update_farming_task(task_id, title, status)
            save.assert_not_called()
            with self.assertRaises(ToolError):
                await update_farming_task('valid', 'Call a shop', 'requested')
            send.assert_not_awaited()


class TaskStoreTests(unittest.TestCase):
    def test_queries_scope_to_account_and_upsert_call_task(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {'id': 'task', 'title': 'Call', 'status': 'requested'}
        conn.execute.return_value.fetchall.return_value = [{'id': 'task', 'title': 'Call', 'status': 'requested'}]
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = conn
        with patch('app.services.tasks.get_pool', return_value=pool):
            self.assertEqual(save_task('user', 'room', 'key', 'Call', 'requested')['id'], 'task')
            sql, params = conn.execute.call_args.args
            self.assertIn('ON CONFLICT (user_id, room_name, task_key)', sql)
            self.assertEqual(params[1:], ('user', 'room', 'key', 'Call', 'requested'))
            self.assertEqual(len(list_tasks('user')), 1)
            sql, params = conn.execute.call_args.args
            self.assertIn('WHERE user_id = %s', sql)
            self.assertEqual(params, ('user',))

    def test_task_endpoint_requires_session_and_uses_session_identity(self):
        client = TestClient(app)
        self.addCleanup(client.close)
        self.addCleanup(app.dependency_overrides.clear)
        self.assertEqual(client.get('/api/v1/conversation/tasks').status_code, 401)
        app.dependency_overrides[require_user] = lambda: {'username': 'account', 'onboarded': True}
        with patch('app.api.routes.conversation.list_tasks', return_value=[]) as lookup:
            response = client.get('/api/v1/conversation/tasks?user_id=other')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        lookup.assert_called_once_with('account')
