"""Firebase session cookies and Postgres user synchronization.

Login (create_session) verifies the Google ID token, mints the session cookie and
writes the user row once. Ordinary requests verify the cookie locally and only read.
"""
from datetime import timedelta
from functools import lru_cache
import json
from secrets import randbelow
import time
from uuid import uuid4

import firebase_admin
from psycopg.errors import UniqueViolation
from firebase_admin import auth, credentials

from app.core.config import get_settings
from app.core.postgres import get_pool


@lru_cache
def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        settings = get_settings()
        credential = (json.loads(settings.firebase_service_account_json.get_secret_value())
                      if settings.firebase_service_account_json else str(settings.firebase_service_account_path))
        return firebase_admin.initialize_app(credentials.Certificate(credential))


SESSION_MAX_AGE = timedelta(days=5)
# Firebase requires a recent sign-in before minting a session cookie.
RECENT_SIGN_IN_SECONDS = 5 * 60


class RecentSignInRequired(Exception):
    pass


def verify_session(session: str, *, check_revoked: bool = False) -> dict:
    """Verify a session cookie.

    Without check_revoked this is a local signature check using cached Google
    public keys. With it, Firebase is also asked whether the user was disabled or
    signed out, which costs a network round trip; use it for sensitive actions.
    """
    return auth.verify_session_cookie(session, check_revoked=check_revoked, app=get_firebase_app())


def create_session(id_token: str) -> tuple[str, dict]:
    """Exchange a fresh Google sign-in ID token for a session cookie and the synced user."""
    app = get_firebase_app()
    claims = auth.verify_id_token(id_token, check_revoked=True, app=app)
    if time.time() - claims["auth_time"] > RECENT_SIGN_IN_SECONDS:
        raise RecentSignInRequired
    cookie = auth.create_session_cookie(id_token, expires_in=SESSION_MAX_AGE, app=app)
    return cookie, sync_user(claims)


def revoke_session(session: str) -> None:
    """Sign the user out everywhere by revoking their Firebase refresh tokens."""
    app = get_firebase_app()
    claims = auth.verify_session_cookie(session, app=app)
    auth.revoke_refresh_tokens(claims["uid"], app=app)


def _user_response(row) -> dict:
    return {"username": str(row["id"]), "display_name": row["display_name"] or "User",
            "onboarded": bool(row["phone_number"] or row["generated_phone_identifier"])}


def load_user(claims: dict) -> dict:
    """Read the account for verified claims; create it only if login sync never ran."""
    with get_pool().connection() as conn:
        row = conn.execute("""
            SELECT id, display_name, phone_number, generated_phone_identifier
            FROM opencall.users WHERE firebase_uid = %s
        """, (claims["uid"],)).fetchone()
    return _user_response(row) if row else sync_user(claims)


def with_phone_identifier(operation):
    """Retry if a generated identifier is already assigned to another account."""
    for _ in range(10):
        identifier = str(1_000_000_000 + randbelow(9_000_000_000))
        try:
            with get_pool().connection() as conn:
                return operation(conn, identifier)
        except UniqueViolation as error:
            if error.diag.constraint_name != "users_generated_phone_identifier_key":
                raise
    raise RuntimeError("Unable to allocate a unique phone identifier")


def sync_user(claims: dict) -> dict:
    def upsert(conn, identifier):
        return conn.execute("""
            INSERT INTO opencall.users (id, firebase_uid, display_name, email, generated_phone_identifier)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE SET
                display_name = COALESCE(EXCLUDED.display_name, opencall.users.display_name),
                email = COALESCE(EXCLUDED.email, opencall.users.email),
                generated_phone_identifier = CASE WHEN opencall.users.phone_number IS NULL
                    THEN COALESCE(opencall.users.generated_phone_identifier, EXCLUDED.generated_phone_identifier)
                    ELSE opencall.users.generated_phone_identifier END,
                updated_at = now()
            RETURNING id, display_name, phone_number, generated_phone_identifier
        """, (uuid4(), claims["uid"], claims.get("name"), claims.get("email"), identifier)).fetchone()
    return _user_response(with_phone_identifier(upsert))
