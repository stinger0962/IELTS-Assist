"""Google Cloud Text-to-Speech service for IELTS listening exercises."""

import io
import logging
import uuid
from pathlib import Path

from google.cloud import texttospeech

from app.config import settings

logger = logging.getLogger(__name__)

# IELTS uses British, Australian, and American accents — M + F per region
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
    "australian_male": texttospeech.VoiceSelectionParams(
        language_code="en-AU", name="en-AU-Standard-B",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    ),
    "american_female": texttospeech.VoiceSelectionParams(
        language_code="en-US", name="en-US-Standard-C",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
    ),
    "american_male": texttospeech.VoiceSelectionParams(
        language_code="en-US", name="en-US-Standard-B",
        ssml_gender=texttospeech.SsmlVoiceGender.MALE,
    ),
}

# Voice pairs for multi-speaker formats (conversation / discussion)
VOICE_PAIRS = [
    ("british_female", "british_male"),
    ("australian_female", "australian_male"),
    ("american_female", "american_male"),
    ("british_female", "australian_male"),
    ("australian_female", "british_male"),
    ("american_female", "british_male"),
]

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


def _save_audio(audio_bytes: bytes) -> str:
    """Write MP3 bytes to disk and return the public URL path."""
    filename = f"{uuid.uuid4().hex}.mp3"
    audio_dir = Path(settings.TTS_AUDIO_DIR)
    audio_dir.mkdir(parents=True, exist_ok=True)
    filepath = audio_dir / filename
    filepath.write_bytes(audio_bytes)
    logger.info("TTS: wrote %d bytes → %s", len(audio_bytes), filepath)
    return f"{settings.TTS_AUDIO_URL_PREFIX}/{filename}"


def synthesize(text: str, voice_key: str = "british_female") -> str:
    """Convert text to MP3 and return the public URL path."""
    voice = VOICES.get(voice_key, VOICES["british_female"])
    client = _get_client()
    response = client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=voice,
        audio_config=AUDIO_CONFIG,
    )
    return _save_audio(response.audio_content)


def synthesize_dialogue(transcript: str, speakers: list[str], voice_pair: tuple[str, str]) -> str:
    """Convert a multi-speaker transcript to a single MP3.

    Parses lines like "Sarah: Hello..." and "Receptionist: Welcome...",
    synthesizes each speaker's lines with a different voice, concatenates
    with short pauses between turns, and returns the combined audio URL.
    """
    from pydub import AudioSegment  # lazy import — needs audioop (Python ≤3.12)

    client = _get_client()
    voice_map: dict[str, str] = {}
    for i, name in enumerate(speakers):
        voice_map[name.strip().lower()] = voice_pair[i % len(voice_pair)]

    segments: list[AudioSegment] = []
    pause = AudioSegment.silent(duration=600)  # 0.6s pause between turns

    for line in transcript.strip().split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        speaker_name, text = line.split(":", 1)
        text = text.strip()
        if not text:
            continue

        voice_key = voice_map.get(speaker_name.strip().lower(), voice_pair[0])
        voice = VOICES.get(voice_key, VOICES["british_female"])

        response = client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=voice,
            audio_config=AUDIO_CONFIG,
        )
        segment = AudioSegment.from_mp3(io.BytesIO(response.audio_content))
        if segments:
            segments.append(pause)
        segments.append(segment)

    if not segments:
        return synthesize(transcript, voice_pair[0])

    combined = segments[0]
    for seg in segments[1:]:
        combined += seg

    buf = io.BytesIO()
    combined.export(buf, format="mp3")
    return _save_audio(buf.getvalue())
