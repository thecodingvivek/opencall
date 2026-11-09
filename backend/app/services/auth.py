"""Firebase identity verification and Postgres user synchronization."""
from functools import lru_cache
from secrets import token_hex
from uuid import uuid4

import firebase_admin
from firebase_admin import auth, credentials

from app.core.config import get_settings
from app.core.postgres import get_pool


@lru_cache
def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(credentials.Certificate(str(get_settings().firebase_service_account_path)))


def verify_session(session: str) -> dict:
    return auth.verify_session_cookie(session, check_revoked=True, app=get_firebase_app())


def sync_user(claims: dict) -> dict:
    with get_pool().connection() as conn:
        row = conn.execute("""
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
        """, (uuid4(), claims["uid"], claims.get("name"), claims.get("email"), "placeholder-" + token_hex(16))).fetchone()
    return {"username": str(row["id"]), "display_name": row["display_name"] or "User",
            "onboarded": bool(row["phone_number"] or row["generated_phone_identifier"])}
