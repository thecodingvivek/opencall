import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException, Response
from firebase_admin import auth as firebase_auth
from pydantic import SecretStr

from app.api.routes.auth import (
    Onboarding, SessionRequest, logout, onboarding, require_fresh_user, require_user, session,
)
from app.services.auth import (
    SESSION_MAX_AGE, RecentSignInRequired, create_session, get_firebase_app, load_user,
    revoke_session, sync_user,
)


class FirebaseIdentityTests(unittest.TestCase):
    def test_firebase_credentials_support_json_and_file(self):
        for inline, expected in ((SecretStr('{"project_id":"example"}'), {"project_id": "example"}),
                                 (None, "/local/service.json")):
            with self.subTest(inline=inline is not None), \
                 patch("app.services.auth.firebase_admin.get_app", side_effect=ValueError), \
                 patch("app.services.auth.get_settings") as settings, \
                 patch("app.services.auth.credentials.Certificate", return_value="credential") as certificate, \
                 patch("app.services.auth.firebase_admin.initialize_app", return_value="app"):
                settings.return_value.firebase_service_account_json = inline
                settings.return_value.firebase_service_account_path = "/local/service.json"
                get_firebase_app.cache_clear()
                self.assertEqual(get_firebase_app(), "app")
                certificate.assert_called_once_with(expected)
        get_firebase_app.cache_clear()

    def test_missing_session_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            require_user(None)
        self.assertEqual(error.exception.status_code, 401)

    def test_ordinary_requests_skip_revocation_and_only_read(self):
        with patch("app.api.routes.auth.verify_session", return_value={"uid": "trusted"}) as verify, \
             patch("app.api.routes.auth.load_user", return_value={"username": "account"}) as load:
            self.assertEqual(require_user("cookie"), {"username": "account"})
            verify.assert_called_once_with("cookie", check_revoked=False)
            load.assert_called_once_with({"uid": "trusted"})

    def test_sensitive_requests_check_revocation(self):
        with patch("app.api.routes.auth.verify_session", return_value={"uid": "trusted"}) as verify, \
             patch("app.api.routes.auth.load_user", return_value={"username": "account"}):
            require_fresh_user("cookie")
            verify.assert_called_once_with("cookie", check_revoked=True)
        with patch("app.api.routes.auth.verify_session", side_effect=firebase_auth.UserDisabledError("off")), \
             self.assertRaises(HTTPException) as error:
            require_fresh_user("cookie")
        self.assertEqual(error.exception.status_code, 401)

    def test_load_user_reads_and_falls_back_to_sync_once(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {
            "id": "id", "display_name": None, "phone_number": None, "generated_phone_identifier": "1234567890"}
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = conn
        with patch("app.services.auth.get_pool", return_value=pool), \
             patch("app.services.auth.sync_user") as sync:
            self.assertEqual(load_user({"uid": "u"}), {"username": "id", "display_name": "User", "onboarded": True})
            query = conn.execute.call_args.args[0]
            self.assertTrue(query.strip().startswith("SELECT"))
            sync.assert_not_called()
            conn.execute.return_value.fetchone.return_value = None
            load_user({"uid": "new"})
            sync.assert_called_once_with({"uid": "new"})

    def test_session_creation_requires_recent_sign_in_and_syncs_user(self):
        now = time.time()
        with patch("app.services.auth.get_firebase_app", return_value="app"), \
             patch("app.services.auth.auth.verify_id_token", return_value={"uid": "u", "auth_time": now - 10}) as verify, \
             patch("app.services.auth.auth.create_session_cookie", return_value="minted") as mint, \
             patch("app.services.auth.sync_user", return_value={"username": "account"}) as sync:
            self.assertEqual(create_session("token"), ("minted", {"username": "account"}))
            verify.assert_called_once_with("token", check_revoked=True, app="app")
            mint.assert_called_once_with("token", expires_in=SESSION_MAX_AGE, app="app")
            sync.assert_called_once()
            verify.return_value = {"uid": "u", "auth_time": now - 600}
            with self.assertRaises(RecentSignInRequired):
                create_session("token")

    def test_session_endpoint_maps_errors(self):
        with patch("app.api.routes.auth.create_session", side_effect=RecentSignInRequired), \
             self.assertRaises(HTTPException) as error:
            session(SessionRequest(idToken="t"), Response())
        self.assertEqual(error.exception.status_code, 401)
        with patch("app.api.routes.auth.create_session", side_effect=RuntimeError("private")), \
             self.assertRaises(HTTPException) as error:
            session(SessionRequest(idToken="t"), Response())
        self.assertEqual(error.exception.status_code, 503)
        with patch("app.api.routes.auth.create_session", return_value=("minted", {"username": "a"})):
            body = session(SessionRequest(idToken="t"), Response())
        self.assertEqual(body["session"], "minted")
        self.assertEqual(body["expires_in"], 5 * 24 * 3600)

    def test_logout_revokes_and_always_succeeds(self):
        with patch("app.api.routes.auth.revoke_session") as revoke:
            self.assertEqual(logout("cookie").status_code, 204)
            revoke.assert_called_once_with("cookie")
            revoke.side_effect = firebase_auth.InvalidSessionCookieError("bad")
            self.assertEqual(logout("cookie").status_code, 204)
            self.assertEqual(logout(None).status_code, 204)
        with patch("app.services.auth.get_firebase_app", return_value="app"), \
             patch("app.services.auth.auth.verify_session_cookie", return_value={"uid": "u"}), \
             patch("app.services.auth.auth.revoke_refresh_tokens") as tokens:
            revoke_session("cookie")
            tokens.assert_called_once_with("u", app="app")

    def test_upsert_does_not_replace_phone_or_phonebook(self):
        conn = MagicMock()
        conn.execute.return_value.fetchone.return_value = {"id": "id", "display_name": "A", "phone_number": None, "generated_phone_identifier": None}
        pool = MagicMock()
        pool.connection.return_value.__enter__.return_value = conn
        with patch("app.services.auth.get_pool", return_value=pool):
            sync_user({"uid": "verified", "name": "A"})
        query, params = conn.execute.call_args.args
        self.assertIn("ON CONFLICT (firebase_uid)", query)
        self.assertNotIn("phonebook =", query)
        self.assertEqual(params[1], "verified")
        self.assertRegex(params[4], r"^[1-9][0-9]{9}$")

    def test_invalid_number_rejected(self):
        with self.assertRaises(HTTPException) as error:
            onboarding(Onboarding(phone_number="123"), {"username": "id"})
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
