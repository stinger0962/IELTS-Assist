"""An active question-only preview can be answered and scored without v1 keys."""

import pytest

from app.services.full_mock_preview import active_mock_preview
from app.services.full_mock_raw_score import SCHEMA_VERSION, score_full_mock
from app.services.full_mock_renderer_bridge import RENDERER_VERSION
from tests.test_full_mock_audit import fixture


@pytest.mark.parametrize(("skill", "expected_correct"), [("reading", 37), ("listening", 36)])
def test_question_only_preview_to_raw_result(skill, expected_correct):
    private_content = fixture(skill)
    preview = active_mock_preview(private_content, skill=skill, renderer_version=RENDERER_VERSION)

    # The simulated learner has only the public question identities and options.
    # Synthetic fixture choices: "box" on every completion, first option on
    # every selector. The second heading/stem in each section needs option B.
    answers = {
        question["key"]: question["options"][0]["id"] if "options" in question else "box"
        for section in preview["sections"]
        for question in section["questions"]
    }
    assert len(answers) == preview["total_questions"] == 40

    result = score_full_mock(
        private_content,
        {"schema_version": SCHEMA_VERSION, "answers": answers},
        skill=skill,
    )
    assert (result["correct"], result["total"]) == (expected_correct, 40)
    assert sum(section["total"] - section["correct"] for section in result["sections"]) == len(preview["sections"])
    assert "band" not in result
