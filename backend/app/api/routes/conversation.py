from fastapi import APIRouter, HTTPException, Response

from app.services.conversation import ConnectionDetails, ConversationOptions, create_connection

router = APIRouter(prefix="/conversation", tags=["conversation"])


@router.post("/connect", response_model=ConnectionDetails)
def connect(options: ConversationOptions, response: Response) -> ConnectionDetails:
    try:
        details = create_connection(options)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from None
    response.headers["Cache-Control"] = "no-store"
    return details
