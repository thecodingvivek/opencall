from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.routes.auth import CurrentUser
from app.services.conversation import ConnectionDetails, ConversationOptions, create_connection, ensure_voice_available
from app.services.phonebook import DescriptionUpdate, PhonebookEntry, PhonebookStore, get_phonebook_store
from app.services.tasks import list_tasks

router = APIRouter(prefix="/conversation", tags=["conversation"])
Store = Annotated[PhonebookStore, Depends(get_phonebook_store)]


@router.get("/tasks")
def tasks(response: Response, user: CurrentUser):
    response.headers["Cache-Control"] = "no-store"
    try:
        return list_tasks(user["username"])
    except Exception:
        raise HTTPException(503, "Task list is unavailable") from None


@router.post("/guest-connect", response_model=ConnectionDetails)
async def guest_connect(options: ConversationOptions, response: Response, user: CurrentUser) -> ConnectionDetails:
    if not user["onboarded"]:
        raise HTTPException(403, "Complete onboarding before starting a call")
    try:
        details = create_connection(options, user)
        await ensure_voice_available()
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return details


@router.post("/connect", response_model=ConnectionDetails)
async def connect(options: ConversationOptions, response: Response, user: CurrentUser) -> ConnectionDetails:
    if not user["onboarded"]:
        raise HTTPException(403, "Complete onboarding before starting a call")
    try:
        details = create_connection(options, user)
        await ensure_voice_available()
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return details


@router.get("/phonebook", response_model=PhonebookEntry)
def phonebook(response: Response, user: CurrentUser, store: Store):
    response.headers["Cache-Control"] = "no-store"
    return store.get(user["username"])


@router.put("/phonebook", response_model=PhonebookEntry)
def update_phonebook(payload: DescriptionUpdate, response: Response, user: CurrentUser, store: Store):
    response.headers["Cache-Control"] = "no-store"
    return store.set_description(user["username"], payload.description)
