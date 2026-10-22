"""
Automatic Speech Recognition Endpoint
Accepts an audio file and returns the transcribed text via Whisper.
"""
import io
import tempfile
import os

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from loguru import logger

from app.services.whisper_service import WhisperService

router = APIRouter()
whisper = WhisperService()


class ASRResponse(BaseModel):
    transcript: str
    language: str
    confidence: float


@router.post("/transcribe", response_model=ASRResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Accepts a WAV/M4A/OGG audio file and returns the transcribed text.
    The mobile app streams short voice clips (1-5 seconds) here.
    """
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")

    try:
        audio_bytes = await audio.read()

        # Write to temp file (Whisper needs a file path)
        suffix = os.path.splitext(audio.filename or "clip.wav")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        result = await whisper.transcribe(tmp_path)
        os.unlink(tmp_path)

        return ASRResponse(**result)

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
