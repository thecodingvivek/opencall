from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
from tinydb import Query

from app.core.database import database
from app.main import app
from app.services.auth import AuthStore, get_auth_store
from app.services.phonebook import PhonebookStore, get_phonebook_store


class PhonebookTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "db.json"
        self.auth = AuthStore(self.path)
        with database(self.path) as db:
            other = dict(db.table("users").get(Query().username == "demo"))
            other["username"] = "other"
            db.table("users").insert(other)
        self.store = PhonebookStore(self.path)

    def test_description_is_persisted_by_username(self):
        self.assertEqual(self.store.get("demo").model_dump(), {"username": "demo", "description": ""})
        self.store.set_description("demo", "A science teacher.")
        self.assertEqual(PhonebookStore(self.path).get("demo").description, "A science teacher.")
        self.assertEqual(self.store.get("other").description, "")

    def test_existing_database_is_simplified_without_losing_descriptions(self):
        with database(self.path) as db:
            db.table("phonebook").update({"description": "A teacher.", "user_id": "old-id",
                "previous_summary": "Old summary", "revision": 3}, Query().username == "demo")
            db.table("calls").insert({"call_id": "old-call"})
            db.table("users").update({"user_id": "old-id", "phone_number": None}, Query().username == "demo")
            db.table("sessions").insert({"user_id": "old-id", "token_hash": "old-token", "expires_at": 9999999999})
        AuthStore(self.path)
        migrated = PhonebookStore(self.path)
        self.assertEqual(migrated.get("demo").model_dump(), {"username": "demo", "description": "A teacher."})
        with database(self.path) as db:
            self.assertNotIn("calls", db.tables())
            self.assertNotIn("user_id", db.table("users").get(Query().username == "demo"))
            session = db.table("sessions").get(Query().token_hash == "old-token")
            self.assertEqual(session["username"], "demo")
            self.assertNotIn("user_id", session)

    def test_api_reads_and_updates_only_the_signed_in_username(self):
        app.dependency_overrides[get_auth_store] = lambda: self.auth
        app.dependency_overrides[get_phonebook_store] = lambda: self.store
        self.addCleanup(app.dependency_overrides.clear)
        client = TestClient(app)
        self.addCleanup(client.close)
        endpoint = "/api/v1/conversation/phonebook"
        self.assertEqual(client.get(endpoint).status_code, 401)
        self.assertEqual(client.put(endpoint, json={"description": "test"}).status_code, 401)
        client.post("/api/v1/auth/login", json={"username": "demo", "password": "opencall123"})
        response = client.put(endpoint, json={"description": "A science teacher."})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "demo", "description": "A science teacher."})
        self.assertEqual(client.get(endpoint).json(), response.json())
        self.assertEqual(self.store.get("other").description, "")
        self.assertEqual(client.put(endpoint, json={"username": "other", "description": "forged"}).status_code, 422)
        self.assertEqual(client.get("/api/v1/conversation/old-call").status_code, 404)
