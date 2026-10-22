from fastapi import APIRouter

from app.api.routes import conversation, health, speech

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(speech.router)
api_router.include_router(conversation.router)
