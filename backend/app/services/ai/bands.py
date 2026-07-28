"""IELTS band handling shared by the writing and speaking graders.

The scoring prompts supply official descriptors for Bands 4-9 only, so any
score outside that range is one the rubric cannot justify and the feedback
cannot explain. Production grading was observed returning overall bands of
2.5 and 3.0; clamping keeps the number consistent with the evidence shown
beside it, and the warning tells us how often the model goes off-scale.
"""

import logging

logger = logging.getLogger(__name__)

BAND_MIN = 4.0  # lowest band the supplied descriptors define
BAND_MAX = 9.0


def clamp_band(value, *, criterion: str = "", context: str = "") -> float:
    """Return a band inside [BAND_MIN, BAND_MAX], logging anything out of range."""
    try:
        band = float(value)
    except (TypeError, ValueError):
        logger.warning(
            "grader returned a non-numeric band %r for %s %s; using %.1f",
            value, criterion or "criterion", context, BAND_MIN,
        )
        return BAND_MIN

    if band < BAND_MIN or band > BAND_MAX:
        clamped = min(max(band, BAND_MIN), BAND_MAX)
        logger.warning(
            "grader returned off-scale band %.1f for %s %s; clamped to %.1f",
            band, criterion or "criterion", context, clamped,
        )
        return clamped

    return band
