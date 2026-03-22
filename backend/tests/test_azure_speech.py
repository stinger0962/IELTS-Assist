"""Tests for Azure Speech pronunciation assessment wrapper."""
from app.services.azure_speech import assess_pronunciation


def test_assess_pronunciation_skips_when_no_key():
    """When AZURE_SPEECH_KEY is empty, return None gracefully."""
    result = assess_pronunciation("/nonexistent/audio.wav")
    assert result is None
