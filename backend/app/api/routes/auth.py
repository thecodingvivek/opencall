from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.services.auth import AuthStore, COOKIE_NAME, SESSION_SECONDS, get_auth_store

router = APIRouter(prefix="/auth", tags=["auth"])
Store = Annotated[AuthStore, Depends(get_auth_store)]
Session = Annotated[str | None, Cookie(alias=COOKIE_NAME)]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    username: str
    display_name: str


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, store: Store):
    result = store.login(payload.username, payload.password)
    if result is None:
        raise HTTPException(401, "Invalid username or password", headers={"Cache-Control": "no-store"})
    token, user = result
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", max_age=SESSION_SECONDS)
    response.headers["Cache-Control"] = "no-store"
    return user


@router.get("/me", response_model=UserResponse)
def me(response: Response, store: Store, session: Session = None):
    user = store.current_user(session) if session else None
    if user is None:
        raise HTTPException(401, "Please log in", headers={"Cache-Control": "no-store"})
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/logout", status_code=204)
def logout(response: Response, store: Store, session: Session = None):
    if session:
        store.logout(session)
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
