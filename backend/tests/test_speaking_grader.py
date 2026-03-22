"""Tests for speaking grader — validates interface and band calculation."""
from app.services.ai.speaking_grader import SpeakingGrader


def test_grader_version():
    grader = SpeakingGrader()
    assert grader.GRADER_VERSION == "1.0"


def test_map_pronunciation_band():
    """Test Azure score → IELTS band mapping."""
    grader = SpeakingGrader()
    assert grader._map_pronunciation_band(95) == 9.0
    assert grader._map_pronunciation_band(90) == 8.5
    assert grader._map_pronunciation_band(82) == 8.0
    assert grader._map_pronunciation_band(75) == 7.5
    assert grader._map_pronunciation_band(68) == 7.0
    assert grader._map_pronunciation_band(60) == 6.5
    assert grader._map_pronunciation_band(52) == 6.0
    assert grader._map_pronunciation_band(45) == 5.5
    assert grader._map_pronunciation_band(38) == 5.0
    assert grader._map_pronunciation_band(30) == 4.5
    assert grader._map_pronunciation_band(20) == 4.0
    assert grader._map_pronunciation_band(None) is None
