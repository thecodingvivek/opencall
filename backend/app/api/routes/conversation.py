from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.routes.auth import CurrentUser
from app.services.conversation import ConnectionDetails, ConversationOptions, create_connection, ensure_voice_available
from app.services.phonebook import DescriptionUpdate, PhonebookEntry, PhonebookStore, get_phonebook_store
from app.services.room_codes import create_code, claim_code
from pydantic import BaseModel, Field

router = APIRouter(prefix="/conversation", tags=["conversation"])
Store = Annotated[PhonebookStore, Depends(get_phonebook_store)]


class RoomCodeRequest(ConversationOptions):
    code: str = Field(pattern=r"^[0-9]{8}$")


@router.post("/rooms")
async def create_room_code(response: Response, user: CurrentUser, store: Store):
    try:
        create_connection(ConversationOptions(), user)
        await ensure_voice_available()
        code, room = create_code(store.path)
        details = create_connection(ConversationOptions(), user, room_name=room["room_name"],
                                    observer=True, phone_identity=room["participant_identity"])
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return {"code": code, "expires_in": 600, **details.model_dump()}


@router.post("/rooms/join", response_model=ConnectionDetails)
async def join_room(payload: RoomCodeRequest, response: Response, user: CurrentUser, store: Store):
    options = ConversationOptions(language_code=payload.language_code, voice=payload.voice)
    try:
        # Validate configuration and availability before consuming the one-use code.
        create_connection(options, user)
        await ensure_voice_available()
        room = claim_code(store.path, payload.code)
        if room is None:
            raise HTTPException(404, "Room code is invalid, expired, or already used.")
        details = create_connection(options, user, room_name=room["room_name"],
                                    identity=room["participant_identity"], dispatch=False)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return details


@router.post("/guest-connect", response_model=ConnectionDetails)
async def guest_connect(options: ConversationOptions, response: Response, user: CurrentUser) -> ConnectionDetails:
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
