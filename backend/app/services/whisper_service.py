"""
Whisper ASR Service — Speech-to-text transcription
"""
from typing import Dict, Any
from loguru import logger
from app.core.config import settings


class WhisperService:
    def __init__(self):
        self._model = None

    def _get_model(self):
        """Lazy-load Whisper model on first use."""
        if self._model is None:
            import whisper
            logger.info(f"Loading Whisper {settings.WHISPER_MODEL_SIZE} model...")
            self._model = whisper.load_model(settings.WHISPER_MODEL_SIZE)
            logger.info("Whisper model loaded.")
        return self._model

    async def transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe an audio file using Whisper.
        Returns dict with transcript, language, confidence.
        """
        import asyncio

        model = self._get_model()

        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(audio_path, fp16=False),
        )

        transcript = result.get("text", "").strip()
        language = result.get("language", "en")

        # Whisper doesn't return per-segment confidence directly;
        # we compute a proxy from no_speech_prob
        segments = result.get("segments", [])
        if segments:
            avg_no_speech = sum(s.get("no_speech_prob", 0) for s in segments) / len(segments)
            confidence = max(0.0, 1.0 - avg_no_speech)
        else:
            confidence = 0.0 if not transcript else 0.9

        logger.info(f"Transcribed [{language}]: {transcript!r} (conf={confidence:.2f})")
        return {"transcript": transcript, "language": language, "confidence": confidence}
