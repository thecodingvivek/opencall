import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi.testclient import TestClient

from app.api.routes.auth import require_user
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
        self.assertEqual(entry.model_dump(), {'username': 'account', 'description': 'A farmer.'})
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
        self.assertEqual(self.client.get(endpoint).status_code, 401)


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
