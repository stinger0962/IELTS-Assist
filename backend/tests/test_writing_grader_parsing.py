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


def test_empty_object_yields_no_annotations():
    assert WritingGrader._coerce_annotations({}) == []


def test_unexpected_types_yield_no_annotations():
    assert WritingGrader._coerce_annotations(None) == []
    assert WritingGrader._coerce_annotations("nonsense") == []
