"""Original, provider-free raw scoring examples; no calibrated band assertions."""
from copy import deepcopy

import pytest

from app.services.full_mock_audit import audit_full_mock
from app.services.full_mock_raw_score import SCHEMA_VERSION, RawSubmissionError, score_full_mock
from tests.test_full_mock_audit import fixture


def submission(answers):
    return {"schema_version": SCHEMA_VERSION, "answers": answers}


@pytest.mark.parametrize("skill", ["reading", "listening"])
@pytest.mark.parametrize("correct", [0, 1, 39, 40])
def test_raw_boundaries_and_reconciled_breakdowns(skill, correct):
    content = fixture(skill)
    items = audit_full_mock(content, skill=skill)
    body = submission({item.key: item.answers[0] for item in items[:correct]})
    original = deepcopy((content, body))
    result = score_full_mock(content, body, skill=skill)
    assert (content, body) == original
    assert result["schema_version"] == SCHEMA_VERSION
    assert (result["correct"], result["total"]) == (correct, 40)
    for key in ("sections", "question_types"):
        assert sum(row["correct"] for row in result[key]) == correct
        assert sum(row["total"] for row in result[key]) == 40
    assert "band" not in str(result) and "score" not in result


@pytest.mark.parametrize("skill,kind,expected", [
    ("reading", "matching_headings", 6), ("listening", "matching", 8),
])
def test_each_nested_input_is_a_mark_not_each_container(skill, kind, expected):
    content = fixture(skill)
    items = [i for i in audit_full_mock(content, skill=skill) if i.question_type == kind]
    assert len(items) == expected
    answers = {i.key: i.answers[0] for i in items}
    result = score_full_mock(content, submission(answers), skill=skill)
    assert result["correct"] == expected
    answers[items[0].key] = ""
    result = score_full_mock(content, submission(answers), skill=skill)
    assert result["correct"] == expected - 1


def test_only_explicit_answer_alternatives_and_case_surrounding_space_normalize():
    content = fixture("listening")
    first = audit_full_mock(content, skill="listening")[0]
    assert first.answers == ("box", "crate")
    assert score_full_mock(content, submission({first.key: " CRATE "}), skill="listening")["correct"] == 1
    for wrong in ("crates", "crate.", "c rate", "container", "", "   "):
        assert score_full_mock(content, submission({first.key: wrong}), skill="listening")["correct"] == 0


@pytest.mark.parametrize("body", [
    {}, {"answers": {}}, {"schema_version": "v1", "answers": {}},
    {"schema_version": SCHEMA_VERSION, "answers": {}, "sections": []},
    {"schema_version": SCHEMA_VERSION, "answers": []},
    {"schema_version": SCHEMA_VERSION, "answers": {"q_0_0": "A"}},
    {"schema_version": SCHEMA_VERSION, "answers": {"s9:q1": "A"}},
    {"schema_version": SCHEMA_VERSION, "answers": {1: "A"}},
    {"schema_version": SCHEMA_VERSION, "answers": {"s1:q1": None}},
    {"schema_version": SCHEMA_VERSION, "answers": {"s1:q1": ["box"]}},
    {"schema_version": SCHEMA_VERSION, "answers": {"s1:q1": {"answer": "box"}}},
    {"schema_version": SCHEMA_VERSION, "answers": {"s1:q1": True}},
])
def test_reject_invalid_or_legacy_submission(body):
    with pytest.raises(RawSubmissionError):
        score_full_mock(fixture("reading"), body, skill="reading")


def test_one_blank_is_never_a_free_mark():
    result = score_full_mock(fixture("reading"), submission({"s1:q1":"   "}), skill="reading")
    assert result["correct"] == 0


def test_no_numeric_or_internal_whitespace_guessing():
    content = fixture("reading")
    content["sections"][0]["questions"]["groups"][0]["items"][0]["answer"] = "two boxes"
    assert score_full_mock(content, submission({"s1:q1":"TWO BOXES"}), skill="reading")["correct"] == 1
    for value in ("2 boxes", "two  boxes", "two\tboxes"):
        assert score_full_mock(content, submission({"s1:q1":value}), skill="reading")["correct"] == 0
