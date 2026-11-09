from typing import Annotated
import re

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from firebase_admin import auth as firebase_auth

from app.core.postgres import get_pool
from app.services.auth import sync_user, verify_session, with_phone_identifier

router = APIRouter(prefix="/auth", tags=["auth"])


def require_user(session: Annotated[str | None, Cookie(alias="firebase_session")] = None) -> dict:
    if not session:
        raise HTTPException(401, "Please sign in")
    try:
        claims = verify_session(session)
    except (firebase_auth.InvalidSessionCookieError, firebase_auth.ExpiredSessionCookieError,
            firebase_auth.RevokedSessionCookieError, ValueError):
        raise HTTPException(401, "Invalid or expired sign-in") from None
    except Exception:
        raise HTTPException(503, "Sign-in service is unavailable") from None
    try:
        return sync_user(claims)
    except Exception:
        raise HTTPException(503, "Account service is unavailable") from None


CurrentUser = Annotated[dict, Depends(require_user)]


@router.get("/me")
def me(response: Response, user: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return user


class Onboarding(BaseModel):
    phone_number: str | None = None


@router.post("/onboarding")
def onboarding(payload: Onboarding, user: CurrentUser):
    phone = payload.phone_number.strip() if payload.phone_number else None
    if phone and not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        raise HTTPException(422, "Use an international number starting with + and country code")
    try:
        if phone:
            with get_pool().connection() as conn:
                conn.execute("UPDATE opencall.users SET phone_number=%s, phone_verified=false, generated_phone_identifier=NULL, updated_at=now() WHERE id=%s", (phone, user["username"]))
        else:
            with_phone_identifier(lambda conn, identifier: conn.execute(
                "UPDATE opencall.users SET generated_phone_identifier=COALESCE(generated_phone_identifier, %s), updated_at=now() WHERE id=%s AND phone_number IS NULL",
                (identifier, user["username"])))
        return {"ok": True}
    except Exception:
        raise HTTPException(503, "Account service is unavailable") from None
