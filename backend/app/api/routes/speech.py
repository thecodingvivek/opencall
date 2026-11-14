import io
import logging
import wave
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.services.speech_rate_limit import limit_speech_requests
from app.services.gnani import (
    get_gnani_stt_client, get_gnani_tts_client, recognize, synthesize_audio,
)

router = APIRouter(prefix="/speech", tags=["speech"])
logger = logging.getLogger(__name__)
MAX_AUDIO_BYTES = 8 * 1024 * 1024
Language = Literal[
    "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN",
    "ml-IN", "mr-IN", "gu-IN", "bn-IN", "pa-IN",
]
TTS_VOICES = [
    "Shivani", "Avinash", "Lakshmi", "Kalpana", "Chetana", "Vasudha", "Riyaa",
    "Tarika", "Shubham", "Prakash", "Devansh", "Yashraj", "Harshad",
]
Delivery = Literal[
    "neutral", "excited", "whispers", "shouting", "laugh", "giggle", "sigh",
    "exhales", "sniffles", "yawns", "coughs", "clears throat", "slow", "pauses",
]


class VoiceOptions(BaseModel):
    language_code: str
    voices: list[str]
    default_voice: str


@router.get("/voices", response_model=VoiceOptions)
def voice_options(language_code: Language = "en-IN") -> VoiceOptions:
    voices = TTS_VOICES
    return VoiceOptions(language_code=language_code, voices=voices, default_voice=voices[0])


class SynthesisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=5000)
    language_code: Language = "en-IN"
    voice: str | None = Field(default=None, min_length=1, max_length=64)
    delivery: Delivery = "neutral"


@router.post("/synthesize", dependencies=[Depends(limit_speech_requests)], response_class=Response, responses={
    200: {"content": {"audio/wav": {}}, "description": "Synthesized WAV audio"},
})
async def synthesize(payload: SynthesisRequest) -> Response:
    voices = TTS_VOICES
    voice = payload.voice if payload.voice is not None else voices[0]
    if voice not in voices:
        raise HTTPException(422, "Choose a supported Timbre v3.0 voice.")

    try:
        client = get_gnani_tts_client(voice=voice, language=payload.language_code)
    except ModuleNotFoundError:
        raise HTTPException(503, "LiveKit speech plugin is not installed. Install backend/requirements.txt.") from None
    except RuntimeError:
        raise HTTPException(503, "Speech service is not configured. Set GNANI_API_KEY on the backend.") from None

    request_id = str(uuid4())
    try:
        text = payload.text if payload.delivery == "neutral" else f"<{payload.delivery}> {payload.text}"
        audio = await synthesize_audio(client, text)
        if not isinstance(audio, bytes) or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise ValueError("Invalid audio response")
    except Exception as error:
        logger.warning("Speech synthesis failed (request %s): %s", request_id, type(error).__name__)
        raise HTTPException(502, "Speech service could not generate audio. Please try again.",
                            headers={"X-API-Request-ID": request_id}) from None

    return Response(audio, media_type="audio/wav", headers={
        "Cache-Control": "no-store",
        "X-API-Request-ID": request_id,
    })


class TranscriptionResponse(BaseModel):
    transcript: str
    language_code: str
    request_id: str


@router.post("/transcribe", dependencies=[Depends(limit_speech_requests)], response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language_code: Language = Form("en-IN"),
) -> TranscriptionResponse:
    data = await audio.read(MAX_AUDIO_BYTES + 1)
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
            pcm = wav.readframes(frames)
            if len(pcm) != frames * 2:
                raise HTTPException(422, "The WAV recording is incomplete.")
    except (wave.Error, EOFError):
        raise HTTPException(422, "Send a valid WAV recording.") from None

    try:
        client = get_gnani_stt_client(language=language_code)
    except ModuleNotFoundError:
        raise HTTPException(503, "LiveKit speech plugin is not installed. Install backend/requirements.txt.") from None
    except RuntimeError:
        raise HTTPException(503, "Speech service is not configured. Set GNANI_API_KEY on the backend.") from None

    request_id = str(uuid4())
    try:
        transcript = await recognize(client, pcm)
    except Exception as error:
        logger.warning("Speech transcription failed (request %s): %s", request_id, type(error).__name__)
        # Upstream error bodies can contain sensitive data; return a safe message.
        raise HTTPException(502, "Speech service could not transcribe this recording. Please try again.",
                            headers={"X-API-Request-ID": request_id}) from None
    return TranscriptionResponse(
        transcript=transcript.strip(), language_code=language_code,
        request_id=request_id,
    )
