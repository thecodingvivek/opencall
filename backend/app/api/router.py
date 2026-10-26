from fastapi import APIRouter

from app.api.routes import auth, conversation, health, speech

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(speech.router)
api_router.include_router(conversation.router)
