"""Shared conversation settings and restricted room-token issuance."""
import json
from datetime import timedelta
from uuid import uuid4

from livekit import api
from pydantic import BaseModel, Field

from app.api.routes.speech import Language, TTS_VOICES
from app.core.config import get_settings

AGENT_NAME = "opencall-conversation"


class ConversationOptions(BaseModel):
    language_code: Language = "en-IN"
    voice: str = Field(default="Shivani", min_length=1, max_length=64)


class ConnectionDetails(BaseModel):
    server_url: str
    participant_token: str
    room_name: str
    participant_identity: str


def create_connection(options: ConversationOptions) -> ConnectionDetails:
    settings = get_settings()
    if options.voice not in TTS_VOICES:
        raise ValueError("Choose a supported Timbre v3.0 voice.")
    if not settings.gnani_api_key or not settings.groq_api_key:
        raise RuntimeError("Set GNANI_API_KEY and GROQ_API_KEY on the backend.")
    if not settings.livekit_api_key or not settings.livekit_api_secret.get_secret_value():
        raise RuntimeError("Configure the LiveKit server credentials on the backend.")
    room_name = f"opencall-{uuid4().hex}"
    identity = f"user-{uuid4().hex}"
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret.get_secret_value())
        .with_identity(identity)
        .with_name("You")
        .with_ttl(timedelta(minutes=10))
        .with_grants(api.VideoGrants(
            room_join=True, room=room_name, can_publish=True, can_subscribe=True,
            can_publish_data=True, can_publish_sources=["microphone"],
            can_update_own_metadata=False,
        ))
        .with_room_config(api.RoomConfiguration(
            max_participants=2, empty_timeout=60, departure_timeout=20,
            agents=[api.RoomAgentDispatch(
                agent_name=AGENT_NAME, metadata=json.dumps({
                    **options.model_dump(), "participant_identity": identity,
                }),
            )],
        ))
        .to_jwt()
    )
    return ConnectionDetails(server_url=settings.livekit_url, participant_token=token,
                             room_name=room_name, participant_identity=identity)
