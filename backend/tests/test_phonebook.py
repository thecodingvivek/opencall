import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi.testclient import TestClient

from app.api.routes.auth import require_fresh_user, require_user
from app.main import app
from app.services.phonebook import PhonebookEntry, PhonebookStore, get_phonebook_store, update_description_after_session


class PhonebookStoreTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = self.conn
        patcher = patch('app.services.phonebook.get_pool', return_value=pool)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.store = PhonebookStore()

    def test_read_scopes_query_to_user(self):
        self.conn.execute.return_value.fetchone.return_value = {
            'username': 'account', 'description': 'A farmer.', 'revision': 3}
        entry = self.store.get('account')
        self.assertEqual(entry.model_dump(), {'username': 'account', 'description': 'A farmer.', 'phone_number': None, 'generated_phone_identifier': None, 'preferred_language': None})
        query, params = self.conn.execute.call_args.args
        self.assertIn('WHERE id=%s', query)
        self.assertEqual(params, ('account',))

    def test_update_checks_revision(self):
        self.conn.execute.return_value.fetchone.return_value = None
        with self.assertRaises(ValueError):
            self.store.set_description('account', 'New description', expected_revision=3)
        query, params = self.conn.execute.call_args.args
        self.assertIn('phonebook_revision=%s', query)
        self.assertEqual(params, ('New description', 'account', 3, 3))


class PhonebookApiTests(unittest.TestCase):
    def setUp(self):
        self.store = Mock()
        self.store.get.return_value = PhonebookEntry(username='account', description='A farmer.')
        self.store.set_description.return_value = PhonebookEntry(username='account', description='A teacher.')
        app.dependency_overrides[require_user] = lambda: {'username': 'account', 'onboarded': True}
        app.dependency_overrides[require_fresh_user] = lambda: {'username': 'account', 'onboarded': True}
        app.dependency_overrides[get_phonebook_store] = lambda: self.store
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_read_and_update_use_signed_in_account(self):
        endpoint = '/api/v1/conversation/phonebook'
        self.assertEqual(self.client.get(endpoint).json()['description'], 'A farmer.')
        self.assertEqual(self.client.put(endpoint, json={'description': 'A teacher.'}).status_code, 200)
        self.store.get.assert_called_once_with('account')
        self.store.set_description.assert_called_once_with('account', 'A teacher.')
        self.assertEqual(self.client.put(endpoint, json={'username': 'other', 'description': 'forged'}).status_code, 422)
        app.dependency_overrides.pop(require_user)
        app.dependency_overrides.pop(require_fresh_user)
        self.assertEqual(self.client.get(endpoint).status_code, 401)
        self.assertEqual(self.client.put(endpoint, json={'description': 'x'}).status_code, 401)

    def test_database_errors_are_safe_and_recoverable(self):
        self.store.get.side_effect = RuntimeError("private database details")
        self.store.set_description.side_effect = RuntimeError("private database details")
        endpoint = '/api/v1/conversation/phonebook'
        for response in (self.client.get(endpoint), self.client.put(endpoint, json={'description': 'test'})):
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private database details', response.text)


class DescriptionUpdateTests(unittest.IsolatedAsyncioTestCase):
    async def test_update_uses_current_revision(self):
        store = Mock()
        store.get.return_value = PhonebookEntry(username='account', description='A farmer.', revision=3)
        with patch('app.services.phonebook.generate_description', new=AsyncMock(return_value='A rice farmer.')) as generate:
            await update_description_after_session(store, 'account', ['I grow rice.'])
        generate.assert_awaited_once_with('A farmer.', 'I grow rice.')
        store.set_description.assert_called_once_with('account', 'A rice farmer.', expected_revision=3)

    async def test_empty_or_failed_generation_preserves_description(self):
        store = Mock()
        store.get.return_value = PhonebookEntry(username='account', description='A farmer.', revision=3)
        with patch('app.services.phonebook.generate_description', new=AsyncMock(side_effect=TimeoutError)) as generate:
            await update_description_after_session(store, 'account', ['', ' '])
            generate.assert_not_awaited()
            await update_description_after_session(store, 'account', ['I grow rice.'])
        store.set_description.assert_not_called()


class SummaryModelTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_uses_dedicated_model_and_logs_only_usage(self):
        from pydantic import SecretStr
        from app.services.phonebook import generate_description

        response = MagicMock()
        response.json = AsyncMock(return_value={
            'choices': [{'finish_reason': 'stop', 'message': {'content': '{"description":"A rice farmer."}'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120,
                      'prompt_tokens_details': {'cached_tokens': 10}},
        })
        request = MagicMock()
        request.__aenter__ = AsyncMock(return_value=response)
        request.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.post.return_value = request
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=session)
        client.__aexit__ = AsyncMock(return_value=False)
        settings = Mock(groq_api_key=SecretStr('test'), groq_model='openai/gpt-oss-20b',
                        groq_summary_model='qwen/qwen3.8-27b')
        with patch('app.services.phonebook.get_settings', return_value=settings), \
             patch('app.services.phonebook.aiohttp.ClientSession', return_value=client), \
             self.assertLogs('app.services.phonebook', level='INFO') as captured:
            self.assertEqual(await generate_description('Farmer', 'I grow rice.'), 'A rice farmer.')
        payload = session.post.call_args.kwargs['json']
        self.assertEqual(payload['model'], 'qwen/qwen3.8-27b')
        self.assertEqual(payload['reasoning_effort'], 'none')
        self.assertEqual(payload['max_completion_tokens'], 512)
        self.assertIn('task=phonebook_summary', captured.output[0])
        self.assertIn('total_tokens=120', captured.output[0])
        self.assertNotIn('I grow rice', captured.output[0])

    async def test_large_session_is_bounded_while_preserving_both_ends(self):
        store = Mock()
        store.get.return_value = PhonebookEntry(username='account', description='', revision=1)
        text = 'A' * 10000 + 'B' * 10000
        with patch('app.services.phonebook.generate_description', new=AsyncMock(return_value='summary')) as generate:
            await update_description_after_session(store, 'account', [text])
        sent = generate.await_args.args[1]
        self.assertLessEqual(len(sent), 12010)
        self.assertTrue(sent.startswith('A' * 6000))
        self.assertTrue(sent.endswith('B' * 6000))

    async def test_incomplete_summary_does_not_replace_previous_description(self):
        from pydantic import SecretStr
        from app.services.phonebook import generate_description

        response = MagicMock()
        response.json = AsyncMock(return_value={'choices': [{'finish_reason': 'length'}]})
        request = MagicMock()
        request.__aenter__ = AsyncMock(return_value=response)
        request.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock()
        session.post.return_value = request
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=session)
        client.__aexit__ = AsyncMock(return_value=False)
        settings = Mock(groq_api_key=SecretStr('test'), groq_summary_model='qwen/qwen3.8-27b')
        with patch('app.services.phonebook.get_settings', return_value=settings), \
             patch('app.services.phonebook.aiohttp.ClientSession', return_value=client):
            with self.assertRaises(ValueError):
                await generate_description('Existing facts', 'A new fact')
