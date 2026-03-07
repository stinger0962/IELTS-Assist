"""Google Cloud Text-to-Speech service for IELTS listening exercises."""

import logging
import os
import uuid
from pathlib import Path

from google.cloud import texttospeech

from app.config import settings

logger = logging.getLogger(__name__)

# IELTS uses British, Australian, and American accents
VOICES = {
    "british_female": texttospeech.VoiceSelectionParams(
        language_code="en-GB", name="en-GB-Standard-A",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
    ),
    "british_male": texttospeech.VoiceSelectionParams(
        language_code="en-GB", name="en-GB-Standard-B",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    ),
    "australian_female": texttospeech.VoiceSelectionParams(
        language_code="en-AU", name="en-AU-Standard-A",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
    ),
    "american_male": texttospeech.VoiceSelectionParams(
        language_code="en-US", name="en-US-Standard-B",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    ),
}

AUDIO_CONFIG = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.MP3,
    speaking_rate=0.95,  # slightly slower for learners
)

_client = None


def _get_client() -> texttospeech.TextToSpeechClient:
    global _client
    if _client is None:
        _client = texttospeech.TextToSpeechClient()
    return _client


def synthesize(text: str, voice_key: str = "british_female") -> str:
    """Convert text to MP3 and return the public URL path.

    Returns a URL like /audio/<uuid>.mp3 that nginx serves as a static file.
    """
    voice = VOICES.get(voice_key, VOICES["british_female"])
    client = _get_client()

    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=voice,
        audio_config=AUDIO_CONFIG,
    )

    filename = f"{uuid.uuid4().hex}.mp3"
    audio_dir = Path(settings.TTS_AUDIO_DIR)
    audio_dir.mkdir(parents=True, exist_ok=True)
    filepath = audio_dir / filename
    filepath.write_bytes(response.audio_content)

    logger.info("TTS: wrote %d bytes → %s", len(response.audio_content), filepath)
    return f"{settings.TTS_AUDIO_URL_PREFIX}/{filename}"
