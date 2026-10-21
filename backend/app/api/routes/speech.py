import io
import wave
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.services.gnani import get_gnani_stt_client, get_gnani_tts_client

router = APIRouter(prefix="/speech", tags=["speech"])
MAX_AUDIO_BYTES = 8 * 1024 * 1024
Language = Literal[
    "en-IN", "hi-IN", "te-IN", "ta-IN", "kn-IN",
    "ml-IN", "mr-IN", "gu-IN", "bn-IN", "pa-IN",
]
TTS_VOICES = {
    "en-IN": ["Kaveri", "Trupti", "Devika", "Pranav", "Shlok", "Girish"],
    "hi-IN": ["Nalini", "Bhavna", "Yashvi", "Urmila", "Jwala", "Chitra", "Ambuja",
              "Deepak", "Roopesh", "Vikrant", "Hemraj", "Jalaj", "Omkar"],
    "te-IN": ["Suhana", "Lehara", "Lavanya", "Yukti", "Varuni"],
    "ta-IN": ["Asmita", "Trisha", "Brinda", "Vedika", "Noopur"],
    "kn-IN": ["Saanvi", "Kavin"], "ml-IN": ["Reshma", "Riyaan"],
    "mr-IN": ["Zahira", "Ishaan"], "gu-IN": ["Falak", "Veera"],
    "bn-IN": ["Kirra", "Dhruva"], "pa-IN": ["Mehuli", "Zayan"],
}


class VoiceOptions(BaseModel):
    language_code: str
    voices: list[str]
    default_voice: str


@router.get("/voices", response_model=VoiceOptions)
def voice_options(language_code: Language = "en-IN") -> VoiceOptions:
    voices = TTS_VOICES[language_code]
    return VoiceOptions(language_code=language_code, voices=voices, default_voice=voices[0])


class SynthesisRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=5000)
    language_code: Language = "en-IN"
    voice: str | None = Field(default=None, min_length=1, max_length=64)


@router.post("/synthesize", response_class=Response, responses={
    200: {"content": {"audio/wav": {}}, "description": "Synthesized WAV audio"},
})
def synthesize(payload: SynthesisRequest) -> Response:
    voices = TTS_VOICES[payload.language_code]
    voice = payload.voice if payload.voice is not None else voices[0]
    if voice not in voices:
        raise HTTPException(422, "Choose a supported voice for the transcript language.")

    try:
        client = get_gnani_tts_client()
        from gnani.tts import AudioConfig
    except ModuleNotFoundError:
        raise HTTPException(503, "Speech SDK is not installed. Install backend/requirements.txt.") from None
    except RuntimeError:
        raise HTTPException(503, "Speech service is not configured. Set GNANI_API_KEY on the backend.") from None

    request_id = str(uuid4())
    try:
        audio = client.synthesize(
            payload.text,
            voice=voice,
            model="timbre-v2.5",
            language=payload.language_code,
            audio_config=AudioConfig(
                sample_rate=48000, encoding="linear_pcm", container="wav",
                num_channels=1, sample_width=2,
            ),
            request_id=request_id,
        )
        if not isinstance(audio, bytes) or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
            raise ValueError("Invalid audio response")
    except Exception:
        raise HTTPException(502, "Speech service could not generate audio. Please try again.") from None

    return Response(audio, media_type="audio/wav", headers={
        "Cache-Control": "no-store",
        "X-API-Request-ID": request_id,
    })


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
