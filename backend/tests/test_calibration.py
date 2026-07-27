"""Grading calibration harness — is the grader still *correct*, not just alive?

Swapping the grading model is invisible to ordinary tests: no error, no crash,
just different band scores. The only way to catch that is to grade essays whose
band a human examiner has already assigned, and compare.

This measures two things, and both matter:

  accuracy    — does a band-6.5 essay come back as 6.5? (within TOLERANCE)
  consistency — does the SAME essay score the same across repeated runs?
                A grader that answers 6.0, 7.0, 6.5 to one essay is unusable
                regardless of how good its average is.

Not part of the default suite: it makes real API calls and costs money. Run it
deliberately, before and after any grading-model change:

    cd backend
    python -m pytest tests/test_calibration.py -m calibration -s

    # capture a baseline on the old model first
    OPENAI_MODEL_GRADER=gpt-4o python -m pytest tests/test_calibration.py -m calibration -s

Fixtures live in tests/fixtures/calibration_essays.json, which is gitignored:
published sample answers are copyrighted and student work is private, so the
data stays out of the repo. Copy calibration_essays.example.json and fill it in.
Sources that publish essays WITH official examiner bands: the Cambridge IELTS
practice test books, and the sample responses on ielts.org.
"""

import json
import statistics
from pathlib import Path

import pytest

from app.services.ai.writing_grader import WritingGrader

pytestmark = pytest.mark.calibration

FIXTURES = Path(__file__).parent / "fixtures" / "calibration_essays.json"

RUNS_PER_ESSAY = 3
TOLERANCE = 0.5  # IELTS bands move in 0.5 steps, so this is one step


def _samples() -> list[dict]:
    """Collection-time load. Must never raise or skip — pytest.skip inherits from
    BaseException and would abort collection rather than skip the test."""
    if not FIXTURES.exists():
        return []
    try:
        return json.loads(FIXTURES.read_text(encoding="utf-8"))
    except Exception:
        return []


@pytest.mark.parametrize(
    "sample", _samples() or [None], ids=lambda s: s["name"] if s else "no-fixtures"
)
def test_band_is_accurate_and_stable(sample):
    if sample is None:
        pytest.skip(
            f"No calibration fixtures at {FIXTURES}. Copy "
            "calibration_essays.example.json and add essays whose band an examiner "
            "assigned — without real anchors this measures nothing."
        )
    if "PASTE" in sample.get("essay", ""):
        pytest.skip(f"{sample['name']}: essay text is still the placeholder")

    grader = WritingGrader()
    bands = []
    for _ in range(RUNS_PER_ESSAY):
        result = grader.grade(sample["essay"], sample["prompt"])
        bands.append(result["examiner_result"]["overall_band"])

    mean = statistics.mean(bands)
    spread = max(bands) - min(bands)
    drift = mean - sample["expected_band"]

    print(
        f"\n  {sample['name']}"
        f"\n    model     : {grader.model}"
        f"\n    expected  : {sample['expected_band']}"
        f"\n    got       : {bands}  mean={mean:.2f}"
        f"\n    spread    : {spread:.2f}  (consistency)"
        f"\n    drift     : {drift:+.2f}  (accuracy)"
    )

    assert spread <= TOLERANCE, (
        f"Unstable: the same essay scored {bands}. A grader that disagrees with "
        f"itself by more than {TOLERANCE} of a band cannot be trusted."
    )
    assert abs(drift) <= TOLERANCE, (
        f"Miscalibrated: mean {mean:.2f} vs examiner's {sample['expected_band']}. "
        f"Consider OPENAI_MODEL_GRADER=gpt-5.6-terra before escalating further."
    )
