from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.routes.auth import CurrentUser
from app.services.conversation import ConnectionDetails, ConversationOptions, create_connection
from app.services.phonebook import PhonebookEntry, PhonebookStore, get_phonebook_store

router = APIRouter(prefix="/conversation", tags=["conversation"])
Store = Annotated[PhonebookStore, Depends(get_phonebook_store)]


@router.post("/connect", response_model=ConnectionDetails)
def connect(options: ConversationOptions, response: Response, user: CurrentUser, store: Store) -> ConnectionDetails:
    try:
        details = create_connection(options, user, store)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return details


@router.get("/phonebook", response_model=PhonebookEntry)
def phonebook(response: Response, user: CurrentUser, store: Store):
    response.headers["Cache-Control"] = "no-store"
    return store.get(user["user_id"])


@router.get("/{call_id}")
def call_status(call_id: str, response: Response, user: CurrentUser, store: Store):
    try:
        call = store.call(call_id)
    except ValueError:
        raise HTTPException(404, "Call not found") from None
    if call["user_id"] != user["user_id"]:
        raise HTTPException(404, "Call not found")
    response.headers["Cache-Control"] = "no-store"
    return {key: call[key] for key in (
        "call_id", "status", "started_at", "ended_at", "memory_status", "call_summary")}
