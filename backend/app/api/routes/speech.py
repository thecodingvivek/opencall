import io
import wave
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.gnani import get_gnani_stt_client

router = APIRouter(prefix="/speech", tags=["speech"])
MAX_AUDIO_BYTES = 8 * 1024 * 1024
Language = Literal[
    "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN",
    "ml-IN", "mr-IN", "gu-IN", "bn-IN", "pa-IN",
]


class TranscriptionResponse(BaseModel):
    transcript: str
    language_code: str
    request_id: str


@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(
    audio: UploadFile = File(...),
    language_code: Language = Form("en-IN"),
) -> TranscriptionResponse:
    # Sync endpoints run SDK/network operations in FastAPI's worker thread pool.
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Recording exceeds the 8 MB limit.")
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
                raise HTTPException(422, "Send a mono, 16-bit PCM WAV recording.")
            if wav.getframerate() != 16000:
                raise HTTPException(422, "Send a WAV recording at 16000 Hz.")
            frames = wav.getnframes()
            if frames == 0 or frames / wav.getframerate() > 60:
                raise HTTPException(422, "Record between 0 and 60 seconds of audio.")
            if len(wav.readframes(frames)) != frames * 2:
                raise HTTPException(422, "The WAV recording is incomplete.")
    except (wave.Error, EOFError):
        raise HTTPException(422, "Send a valid WAV recording.") from None

    try:
        client = get_gnani_stt_client()
    except ModuleNotFoundError:
        raise HTTPException(503, "Speech SDK is not installed. Install backend/requirements.txt.") from None
    except RuntimeError:
        raise HTTPException(503, "Speech service is not configured. Set GNANI_API_KEY on the backend.") from None

    request_id = str(uuid4())
    try:
        result = client.transcribe_bytes(
            data, filename="recording.wav", language_code=language_code,
            request_id=request_id,
        )
        transcript = result.get("transcript")
        if result.get("success") is False or not isinstance(transcript, str):
            raise ValueError("Invalid transcription response")
    except Exception:
        # Upstream error bodies can contain sensitive data; return a safe message.
        raise HTTPException(502, "Speech service could not transcribe this recording. Please try again.") from None
    return TranscriptionResponse(
        transcript=transcript.strip(), language_code=language_code,
        request_id=request_id,
    )
