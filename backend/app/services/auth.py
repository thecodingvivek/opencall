"""Local development accounts and sessions."""

from functools import lru_cache
from hashlib import pbkdf2_hmac, sha256
from hmac import compare_digest
from pathlib import Path
from secrets import token_hex, token_urlsafe, randbelow
from time import time

from tinydb import Query

from app.core.config import get_settings
from app.core.database import database

COOKIE_NAME = "opencall_session"
SESSION_SECONDS = 86400


class AuthStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with database(path) as db:
            users = db.table("users")
            if not users.get(Query().username == "demo"):
                salt = token_hex(16)
                users.insert({
                    "username": "demo",
                    "display_name": "Demo User",
                    "salt": salt,
                    "password_hash": self.password_hash("opencall123", salt),
                })
            # Keep existing logins working while returning to username-based sessions.
            for user in users.all():
                if user.get("user_id"):
                    sessions = db.table("sessions")
                    sessions.update({"username": user["username"]}, Query().user_id == user["user_id"])
            def simplify(record):
                record.pop("user_id", None)
                record.pop("phone_number", None)
            users.update(simplify)
            db.table("sessions").update(simplify)

    @staticmethod
    def password_hash(password: str, salt: str) -> str:
        return pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()

    def login(self, username: str, password: str) -> tuple[str, dict] | None:
        with database(self.path) as db:
            user = db.table("users").get(Query().username == username)
            # Do the same password work for unknown usernames as for known ones.
            salt = user["salt"] if user else "0" * 32
            digest = self.password_hash(password, salt)
            if not user or not compare_digest(digest, user["password_hash"]):
                return None
            sessions = db.table("sessions")
            sessions.remove(Query().expires_at <= time())
            token = token_urlsafe(32)
            sessions.insert({"token_hash": sha256(token.encode()).hexdigest(),
                             "username": username, "expires_at": time() + SESSION_SECONDS})
            return token, self.public_user(user)

    def create_guest(self) -> tuple[str, dict]:
        with database(self.path) as db:
            users = db.table("users")
            while True:
                username = f"999{randbelow(10**9):09d}"
                if not users.contains(Query().username == username):
                    break
            salt = token_hex(16)
            user = {"username": username, "display_name": "Guest", "salt": salt,
                    "password_hash": self.password_hash(token_urlsafe(32), salt)}
            users.insert(user)
            db.table("phonebook").insert({"username": username, "description": ""})
            token = token_urlsafe(32)
            db.table("sessions").insert({"token_hash": sha256(token.encode()).hexdigest(),
                "username": username, "expires_at": time() + SESSION_SECONDS})
            return token, self.public_user(user)

    def current_user(self, token: str) -> dict | None:
        with database(self.path) as db:
            session = db.table("sessions").get(Query().token_hash == sha256(token.encode()).hexdigest())
            if not session or session["expires_at"] <= time():
                return None
            user = db.table("users").get(Query().username == session.get("username"))
            return self.public_user(user) if user else None

    def logout(self, token: str) -> None:
        with database(self.path) as db:
            db.table("sessions").remove(Query().token_hash == sha256(token.encode()).hexdigest())

    @staticmethod
    def public_user(user: dict) -> dict:
        return {"username": user["username"], "display_name": user["display_name"]}


@lru_cache
def get_auth_store() -> AuthStore:
    return AuthStore(get_settings().tinydb_path)
