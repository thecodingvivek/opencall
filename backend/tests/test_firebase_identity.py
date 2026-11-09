import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.api.routes.auth import Onboarding, onboarding, require_user
from app.services.auth import sync_user


class FirebaseIdentityTests(unittest.TestCase):
    def test_missing_session_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            require_user(None)
        self.assertEqual(error.exception.status_code, 401)

    def test_verified_claims_are_used_for_user_sync(self):
        with patch("app.api.routes.auth.verify_session", return_value={"uid": "trusted"}), \
             patch("app.api.routes.auth.sync_user", return_value={"username": "account"}) as sync:
            self.assertEqual(require_user("cookie"), {"username": "account"})
            sync.assert_called_once_with({"uid": "trusted"})

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

    def test_invalid_number_rejected(self):
        with self.assertRaises(HTTPException) as error:
            onboarding(Onboarding(phone_number="123"), {"username": "id"})
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
