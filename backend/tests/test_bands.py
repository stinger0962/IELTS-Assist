"""Band values must stay inside the range the rubric can justify.

Observed in production: the writing grader returned overall bands of 2.5 and
3.0. The prompt only supplies descriptors for Bands 4-9, so nothing in the
rubric can explain a score below 4 — and a student cannot be shown a number
the feedback is unable to justify.
"""

from app.services.ai.bands import BAND_MAX, BAND_MIN, clamp_band


def test_leaves_in_range_values_untouched():
    assert clamp_band(4.0) == 4.0
    assert clamp_band(6.5) == 6.5
    assert clamp_band(9.0) == 9.0


def test_clamps_below_the_descriptor_floor():
    """2.5 and 3.0 were both seen in real grading output."""
    assert clamp_band(2.5) == BAND_MIN
    assert clamp_band(3.0) == BAND_MIN
    assert clamp_band(0) == BAND_MIN


def test_clamps_above_the_ceiling():
    assert clamp_band(9.5) == BAND_MAX
    assert clamp_band(11) == BAND_MAX


def test_accepts_numeric_strings():
    assert clamp_band("7.0") == 7.0


def test_falls_back_on_junk_rather_than_crashing():
    """A malformed band must not break the whole grading response."""
    assert clamp_band(None) == BAND_MIN
    assert clamp_band("band seven") == BAND_MIN
    assert clamp_band({}) == BAND_MIN
