from typing import Annotated
import re
import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from firebase_admin import auth as firebase_auth

from app.core.postgres import get_pool
from app.services.auth import (
    SESSION_MAX_AGE, RecentSignInRequired, create_session, load_user, revoke_session,
    verify_session, with_phone_identifier,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
SessionCookie = Annotated[str | None, Cookie(alias="firebase_session")]


def _authenticate(session: str | None, *, check_revoked: bool) -> dict:
    if not session:
        raise HTTPException(401, "Please sign in")
    try:
        claims = verify_session(session, check_revoked=check_revoked)
    except (firebase_auth.InvalidSessionCookieError, firebase_auth.UserDisabledError, ValueError):
        raise HTTPException(401, "Invalid or expired sign-in") from None
    except Exception as error:
        logger.warning("Session verification unavailable: %s", type(error).__name__)
        raise HTTPException(503, "Sign-in service is unavailable") from None
    try:
        return load_user(claims)
    except Exception as error:
        logger.warning("Account lookup failed: %s", type(error).__name__)
        raise HTTPException(503, "Account service is unavailable") from None


def require_user(session: SessionCookie = None) -> dict:
    """Fast check for ordinary reads: local cookie verification and one account read."""
    return _authenticate(session, check_revoked=False)


def require_fresh_user(session: SessionCookie = None) -> dict:
    """Also asks Firebase whether the session was revoked or the user disabled."""
    return _authenticate(session, check_revoked=True)


CurrentUser = Annotated[dict, Depends(require_user)]
FreshUser = Annotated[dict, Depends(require_fresh_user)]


class SessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id_token: str = Field(alias="idToken", min_length=1, max_length=16384)


@router.post("/session")
def session(payload: SessionRequest, response: Response):
    """Exchange a fresh Google ID token for a session cookie value.

    Called server-to-server by the frontend, which sets the httpOnly cookie.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        cookie, user = create_session(payload.id_token)
    except RecentSignInRequired:
        raise HTTPException(401, "Recent sign-in required") from None
    except (firebase_auth.InvalidIdTokenError, firebase_auth.UserDisabledError, ValueError):
        raise HTTPException(401, "Invalid or expired sign-in") from None
    except Exception as error:
        logger.warning("Session creation unavailable: %s", type(error).__name__)
        raise HTTPException(503, "Sign-in service is unavailable") from None
    return {"session": cookie, "expires_in": int(SESSION_MAX_AGE.total_seconds()), "user": user}


@router.post("/logout", status_code=204)
def logout(session: SessionCookie = None) -> Response:
    """Revoke the user's Firebase sessions; the frontend clears the cookie either way."""
    if session:
        try:
            revoke_session(session)
        except (firebase_auth.InvalidSessionCookieError, ValueError):
            pass
        except Exception as error:
            logger.warning("Session revocation failed: %s", type(error).__name__)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.get("/me")
def me(response: Response, user: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    return user


class Onboarding(BaseModel):
    phone_number: str | None = None


@router.post("/onboarding")
def onboarding(payload: Onboarding, user: FreshUser):
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
    except Exception as error:
        logger.warning("Onboarding update failed: %s", type(error).__name__)
        raise HTTPException(503, "Account service is unavailable") from None
