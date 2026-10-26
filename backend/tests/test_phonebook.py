import asyncio
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from tinydb import Query

from app.core.database import database
from app.main import app
from app.services.auth import AuthStore, get_auth_store
from app.services.phonebook import (
    MemoryUpdate, PhonebookStore, get_phonebook_store,
    memory_instructions, save_call_memory,
)


class PhonebookTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'db.json'
        self.auth = AuthStore(self.path)
        _, self.user = self.auth.login('demo', 'opencall123')
        with database(self.path) as db:
            other = dict(db.table('users').get(Query().username == 'demo'))
            other.update(username='other', user_id='other-account')
            db.table('users').insert(other)
        self.store = PhonebookStore(self.path)
        self.update = MemoryUpdate(description='A teacher who prefers Telugu.',
            previous_summary='Preparing a science lesson tomorrow.', call_summary='Discussed a science lesson.')

    def new_call(self, user_id=None, text='I am a teacher. I prefer Telugu.'):
        call_id = self.store.create_call(user_id or self.user['user_id'], 'test-room', 'user-test')
        self.store.activate(call_id, 'test-room', 'user-test')
        if text:
            self.store.append_turn(call_id, 'message-1', 'user', text)
        return call_id

    async def test_save_reload_and_duplicate_finalization(self):
        call_id = self.new_call()
        self.store.append_turn(call_id, 'message-1', 'user', 'I am a teacher. I prefer Telugu.')
        self.assertEqual(len(self.store.call(call_id)['turns']), 1)
        self.store.end_call(call_id)
        with patch('app.services.phonebook.summarize_memory', new=AsyncMock(return_value=self.update)) as summarize:
            await save_call_memory(self.store, call_id)
            self.store.end_call(call_id)
            await save_call_memory(self.store, call_id)
            summarize.assert_awaited_once()
        reloaded = PhonebookStore(self.path).get(self.user['user_id'])
        self.assertEqual(reloaded.completed_calls, 1)
        self.assertEqual(reloaded.description, self.update.description)
        self.assertIn(self.update.previous_summary, memory_instructions(reloaded))
        self.assertEqual(self.store.call(call_id)['turns'], [])
        self.assertEqual(self.store.get('other-account').previous_summary, '')

    async def test_failed_summary_preserves_memory_and_pending_turns_for_retry(self):
        first = self.new_call()
        self.store.end_call(first)
        self.store.commit_memory(first, 0, self.update)
        next_call = self.new_call(text='My next lesson is on Friday.')
        self.store.end_call(next_call)
        with patch('app.services.phonebook.summarize_memory', new=AsyncMock(side_effect=TimeoutError)):
            await save_call_memory(self.store, next_call)
        self.assertEqual(self.store.call(next_call)['memory_status'], 'failed')
        self.assertTrue(self.store.call(next_call)['turns'])
        self.assertEqual(self.store.get(self.user['user_id']).previous_summary, self.update.previous_summary)
        self.assertEqual(self.store.pending(self.user['user_id']), [next_call])
        replacement = self.update.model_copy(update={'previous_summary': 'Next lesson is Friday.'})
        with patch('app.services.phonebook.summarize_memory', new=AsyncMock(return_value=replacement)):
            await save_call_memory(self.store, next_call)
        self.assertEqual(self.store.get(self.user['user_id']).completed_calls, 2)
        self.assertEqual(self.store.pending(self.user['user_id']), [])

    async def test_no_user_speech_does_not_overwrite_memory(self):
        call_id = self.new_call(text='')
        self.store.append_turn(call_id, 'greeting', 'assistant', 'Hello, how can I help?')
        self.store.end_call(call_id)
        with patch('app.services.phonebook.summarize_memory', new=AsyncMock()) as summarize:
            await save_call_memory(self.store, call_id)
            summarize.assert_not_awaited()
        self.assertEqual(self.store.get(self.user['user_id']).completed_calls, 0)
        self.assertEqual(self.store.call(call_id)['memory_status'], 'empty')

    async def test_concurrent_calls_merge_against_latest_revision(self):
        first, second = self.new_call(), self.new_call(text='I teach physics.')
        self.store.end_call(first)
        self.store.end_call(second)
        async def summarize(entry, turns):
            if entry.revision == 0:
                self.store.commit_memory(first, 0, self.update)
            return self.update.model_copy(update={'previous_summary': 'A teacher of physics who prefers Telugu.'})
        with patch('app.services.phonebook.summarize_memory', new=AsyncMock(side_effect=summarize)) as generate:
            await save_call_memory(self.store, second)
            self.assertEqual(generate.await_count, 2)
            self.assertEqual(generate.call_args.args[0].revision, 1)
        self.assertEqual(self.store.get(self.user['user_id']).completed_calls, 2)

    async def test_api_does_not_expose_another_accounts_call(self):
        app.dependency_overrides[get_auth_store] = lambda: self.auth
        app.dependency_overrides[get_phonebook_store] = lambda: self.store
        self.addCleanup(app.dependency_overrides.clear)
        call_id = self.new_call(user_id='other-account')
        client = TestClient(app)
        self.addCleanup(client.close)
        client.post('/api/v1/auth/login', json={'username': 'demo', 'password': 'opencall123'})
        response = client.get('/api/v1/conversation/phonebook')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['user_id'], self.user['user_id'])
        self.assertEqual(client.get(f'/api/v1/conversation/{call_id}').status_code, 404)
        own = self.new_call()
        result = client.get(f'/api/v1/conversation/{own}')
        self.assertEqual(result.status_code, 200)
        self.assertNotIn('turns', result.json())

    async def test_binding_validation_and_username_migration(self):
        call_id = self.store.create_call(self.user['user_id'], 'room-one', 'user-one')
        with self.assertRaises(ValueError):
            self.store.activate(call_id, 'other-room', 'user-one')
        with self.assertRaises(ValueError):
            self.store.activate(call_id, 'room-one', 'other-user')
        self.store.activate(call_id, 'room-one', 'user-one')
        with self.assertRaises(ValueError):
            self.store.activate(call_id, 'room-one', 'user-one')
        with database(self.path) as db:
            db.table('users').update({'username': 'renamed', 'phone_number': '+910000000000'},
                Query().user_id == self.user['user_id'])
        entry = self.store.get(self.user['user_id'])
        self.assertEqual(entry.username, 'renamed')
        self.assertEqual(entry.phone_number, '+910000000000')
        self.assertEqual(entry.user_id, self.user['user_id'])

    async def test_text_is_bounded_and_system_messages_are_excluded(self):
        call_id = self.new_call(text='')
        for index in range(30):
            self.store.append_turn(call_id, str(index), 'user', 'x' * 6000)
        self.store.append_turn(call_id, 'system', 'system', 'hidden')
        turns = self.store.call(call_id)['turns']
        self.assertEqual(sum(len(turn['text']) for turn in turns), 60000)
        self.assertTrue(all(turn['role'] == 'user' for turn in turns))

    async def test_database_transactions_serialize_across_processes_and_roll_back(self):
        script = '''
from pathlib import Path
import sys
from app.core.database import database
for _ in range(15):
    with database(Path(sys.argv[1])) as db:
        table = db.table('counter')
        value = table.get(doc_id=1)
        if value is None:
            table.insert({'value': 1})
        else:
            table.update({'value': value['value'] + 1}, doc_ids=[1])
'''
        processes = [subprocess.Popen([sys.executable, '-c', script, str(self.path)]) for _ in range(3)]
        for process in processes:
            self.assertEqual(await asyncio.to_thread(process.wait, 15), 0)
        with database(self.path) as db:
            self.assertEqual(db.table('counter').get(doc_id=1)['value'], 45)
        before = self.path.read_text()
        with self.assertRaises(RuntimeError):
            with database(self.path) as db:
                db.table('counter').truncate()
                raise RuntimeError('rollback')
        self.assertEqual(self.path.read_text(), before)

    async def test_invalid_model_output_is_rejected(self):
        with self.assertRaises(ValueError):
            MemoryUpdate.model_validate({'description': 'x' * 801, 'previous_summary': '', 'call_summary': ''})
        with self.assertRaises(ValueError):
            MemoryUpdate.model_validate({'description': '', 'previous_summary': '', 'call_summary': '', 'user_id': 'other'})

    async def test_legacy_account_id_is_backfilled_once_without_changing_login(self):
        with database(self.path) as db:
            user = db.table('users').get(Query().username == 'demo')
            user.pop('user_id')
            db.table('users').remove(Query().username == 'demo')
            db.table('users').insert(dict(user))
        migrated = AuthStore(self.path)
        _, user = migrated.login('demo', 'opencall123')
        _, again = AuthStore(self.path).login('demo', 'opencall123')
        self.assertEqual(user['user_id'], again['user_id'])
