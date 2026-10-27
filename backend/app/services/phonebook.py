"""A phonebook containing one username and description per account."""
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from tinydb import Query

from app.core.database import database


class PhonebookEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    description: str = ""


class DescriptionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    description: str = Field(max_length=800)


class PhonebookStore:
    def __init__(self, path: Path):
        self.path = path
        with database(path) as db:
            table = db.table("phonebook")
            # Keep existing descriptions while removing the previous memory fields.
            entries = {row["username"]: row.get("description", "") for row in table.all()}
            for user in db.table("users").all():
                entries.setdefault(user["username"], "")
            simplified = [{"username": username, "description": description}
                          for username, description in entries.items()]
            if table.all() != simplified:
                table.truncate()
                table.insert_multiple(simplified)
            if "calls" in db.tables():
                db.drop_table("calls")

    def get(self, username: str) -> PhonebookEntry:
        with database(self.path) as db:
            entry = db.table("phonebook").get(Query().username == username)
            if entry is None:
                raise ValueError("Username is not in the phonebook")
            return PhonebookEntry.model_validate(entry)

    def set_description(self, username: str, description: str) -> PhonebookEntry:
        entry = PhonebookEntry(username=username, description=description)
        with database(self.path) as db:
            if not db.table("users").contains(Query().username == username):
                raise ValueError("Unknown username")
            db.table("phonebook").upsert(entry.model_dump(), Query().username == username)
        return entry


@lru_cache
def get_phonebook_store() -> PhonebookStore:
    from app.services.auth import get_auth_store
    return PhonebookStore(get_auth_store().path)
