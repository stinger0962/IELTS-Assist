"""Explicit opt-in, pure raw scoring for the structurally audited 40-leaf shape.

Not wired into v1 routes, inventory, history, or provider jobs. This helper
accepts audit identities only; it must not consume existing UI submission keys.
No raw-to-band conversion or score calibration is inferred.
"""
from .full_mock_audit import audit_full_mock

SCHEMA_VERSION = "full_mock_raw_v2"


class RawSubmissionError(ValueError):
    pass


def _normalize(value):
    # Preserve punctuation, spelling, accents and internal whitespace. Do not
    # guess synonyms, numeric equivalents, missing units or acceptable typos.
    return value.strip().casefold()


def score_full_mock(content, submission, *, skill):
    """Score an explicitly versioned audit-key submission without mutating input.

    All answer values must be strings. Missing/blank answers earn zero; unknown
    keys or unsupported envelope fields fail closed rather than silently scoring
    a legacy or incorrectly keyed submission as forty wrong answers.
    """
    items = audit_full_mock(content, skill=skill)
    if (not isinstance(submission, dict)
            or set(submission) != {"schema_version", "answers"}
            or submission.get("schema_version") != SCHEMA_VERSION):
        raise RawSubmissionError("Expected an explicit full_mock_raw_v2 submission")
    answers = submission["answers"]
    if not isinstance(answers, dict):
        raise RawSubmissionError("Answers must be an audit-key object")
    allowed = {item.key for item in items}
    if any(not isinstance(key, str) or key not in allowed for key in answers):
        raise RawSubmissionError("Unknown audit answer identity")
    if any(not isinstance(value, str) for value in answers.values()):
        raise RawSubmissionError("Each submitted answer must be a string")

    sections = {}
    types = {}
    correct = 0
    for item in items:
        submitted = _normalize(answers.get(item.key, ""))
        matched = bool(submitted) and submitted in {_normalize(a) for a in item.answers}
        mark = int(matched)
        correct += mark
        section = sections.setdefault(item.section, {"section": item.section, "correct": 0, "total": 0})
        kind = types.setdefault(item.question_type, {"type": item.question_type, "correct": 0, "total": 0})
        for bucket in (section, kind):
            bucket["correct"] += mark
            bucket["total"] += 1

    return {
        "schema_version": SCHEMA_VERSION,
        "skill": skill,
        "correct": correct,
        "total": len(items),
        "sections": list(sections.values()),
        "question_types": [types[kind] for kind in sorted(types)],
    }
