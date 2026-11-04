"""Short-lived, single-use codes for connecting a phone to a reserved room."""
from hashlib import sha256
from secrets import randbelow
from time import time
from uuid import uuid4

from tinydb import Query

from app.core.database import database

CODE_LIFETIME_SECONDS = 600


def _hash(code: str) -> str:
    return sha256(code.encode()).hexdigest()


def create_code(path) -> str:
    with database(path) as db:
        codes = db.table("room_codes")
        codes.remove(Query().expires_at <= time())
        while True:
            code = f"{randbelow(100_000_000):08d}"
            if not codes.contains(Query().code_hash == _hash(code)):
                break
        room = {"room_name": f"opencall-{uuid4().hex}", "participant_identity": f"user-{uuid4().hex}"}
        codes.insert({"code_hash": _hash(code), **room,
                      "expires_at": time() + CODE_LIFETIME_SECONDS})
        return code, room


def claim_code(path, code: str) -> dict | None:
    with database(path) as db:
        codes = db.table("room_codes")
        query = Query().code_hash == _hash(code)
        entry = codes.get(query)
        if not entry or entry["expires_at"] <= time():
            if entry:
                codes.remove(query)
            return None
        codes.remove(query)
        return entry
