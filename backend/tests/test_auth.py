from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from time import time
import unittest

from fastapi.testclient import TestClient
from tinydb import Query, TinyDB

from app.main import app
from app.services.auth import AuthStore, COOKIE_NAME, get_auth_store


class AuthTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "data" / "test.json"
        self.store = AuthStore(self.path)
        app.dependency_overrides[get_auth_store] = lambda: self.store
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def login(self, **credentials):
        return self.client.post("/api/v1/auth/login", json=credentials or {
            "username": "demo", "password": "opencall123"})

    def test_seed_is_idempotent_and_password_is_hashed(self):
        AuthStore(self.path)
        with TinyDB(self.path) as db:
            self.assertEqual(len(db.table("users")), 1)
            user = db.table("users").all()[0]
            self.assertNotIn("password", user)
            self.assertNotEqual(user["password_hash"], "opencall123")
        self.assertNotIn("opencall123", self.path.read_text())

    def test_login_session_survives_store_restart_and_logout_revokes_it(self):
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "demo")
        self.assertEqual(response.json()["display_name"], "Demo User")
        self.assertTrue(response.json()["user_id"])
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        token = self.client.cookies.get(COOKIE_NAME)
        self.assertNotIn(token, self.path.read_text())
        self.assertEqual(AuthStore(self.path).current_user(token)["username"], "demo")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 204)
        self.assertIsNone(self.store.current_user(token))
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.assertEqual(self.client.post("/api/v1/auth/logout").status_code, 204)

    def test_invalid_credentials_and_input(self):
        for credentials in [{"username": "demo", "password": "wrong"},
                            {"username": "unknown", "password": "opencall123"}]:
            response = self.login(**credentials)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "Invalid username or password")
            self.assertNotIn(COOKIE_NAME, self.client.cookies)
        self.assertEqual(self.login(username="", password="").status_code, 422)

    def test_expired_and_forged_sessions_are_rejected(self):
        self.login()
        token = self.client.cookies.get(COOKIE_NAME)
        with TinyDB(self.path) as db:
            db.table("sessions").update({"expires_at": time() - 1},
                Query().token_hash == sha256(token.encode()).hexdigest())
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.client.cookies.set(COOKIE_NAME, "forged")
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 401)
        self.login()
        with TinyDB(self.path) as db:
            self.assertEqual(len(db.table("sessions")), 1)
