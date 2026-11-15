"""Annotation-shape handling.

Regression cover for a live bug: response_format=json_object forbids a bare
top-level array, but the prompt asked for one. gpt-4o happened to wrap it in
{"annotations": [...]}; gpt-5.6-luna returned a single bare object instead, so
the parser silently produced zero annotations.
"""

from app.services.ai.writing_grader import WritingGrader

ANNOTATION = {
    "start_char": 0,
    "end_char": 4,
    "original_text": "This",
    "category": "grammar",
    "suggestion": "Use 'These'",
    "severity": "major",
}


def test_accepts_the_wrapped_object_form():
    assert WritingGrader._coerce_annotations({"annotations": [ANNOTATION]}) == [ANNOTATION]


def test_accepts_a_bare_list():
    assert WritingGrader._coerce_annotations([ANNOTATION]) == [ANNOTATION]


def test_accepts_a_single_annotation_object():
    """The exact shape luna returned in production."""
    assert WritingGrader._coerce_annotations(ANNOTATION) == [ANNOTATION]



import json
import pytest
from app.services.ai import writing_grader

@pytest.mark.parametrize("value", [{}, None, "nonsense", {"annotations": None}])
def test_invalid_envelopes_are_not_successful_empty_results(value):
    with pytest.raises(ValueError):
        WritingGrader._coerce_annotations(value)

@pytest.mark.parametrize("payload,status,count", [
    ({"annotations": []}, "complete", 0),
    ({"annotations": [ANNOTATION]}, "complete", 1),
    ({"annotations": [ANNOTATION, None]}, "partial", 1),
    ({"annotations": [dict(ANNOTATION, original_text="absent")]}, "unavailable", 0),
    ({"annotations": [dict(ANNOTATION, category=[]), ANNOTATION]}, "partial", 1),
    ({"annotations": [dict(ANNOTATION, suggestion="")]}, "unavailable", 0),
    ({"annotations": [dict(ANNOTATION, start_char="wrong")]}, "complete", 1),
    ({"annotations": [ANNOTATION, ANNOTATION]}, "partial", 1),
    ({}, "unavailable", 0),
])
def test_outcomes_keep_scoring_and_validate_entries(monkeypatch, payload, status, count):
    scoring = {"examiner_result": {"overall_band": 6.5}, "coaching_feedback": {"summary": "Synthetic"}}
    grader = WritingGrader()
    monkeypatch.setattr(grader, "_score_essay", lambda *args: scoring)
    monkeypatch.setattr(writing_grader, "chat_json", lambda **kwargs: json.dumps(payload))
    result = grader.grade("This is a synthetic test sentence.", {})
    assert result["annotation_status"] == status
    assert len(result["annotations"]) == count
    assert result["examiner_result"] == scoring["examiner_result"]
    assert result["coaching_feedback"] == scoring["coaching_feedback"]

@pytest.mark.parametrize("failure", ["not json", RuntimeError("synthetic outage")])
def test_annotation_failure_preserves_core_feedback(monkeypatch, failure):
    grader = WritingGrader()
    monkeypatch.setattr(grader, "_score_essay", lambda *args: {"examiner_result": {"overall_band": 6}})
    def fake(**kwargs):
        if isinstance(failure, Exception):
            raise failure
        return failure
    monkeypatch.setattr(writing_grader, "chat_json", fake)
    result = grader.grade("This is synthetic.", {})
    assert result["examiner_result"]["overall_band"] == 6
    assert result["annotation_status"] == "unavailable"
    assert result["annotations"] == []
