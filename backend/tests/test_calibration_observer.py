"""Synthetic SDK responses only; never construct a client or contact a provider."""
import json
from types import SimpleNamespace

import pytest
from openai.types.chat import ChatCompletion

from app.services.ai import llm
from app.services.ai.writing_grader import WritingGrader
from tests.calibration_observer import observe_calibration, _usage


SECRET = "SENTINEL_private_prompt_response_or_exception"
SCORING = {"examiner_result": {
    key: {"band": 6.5} for key in (
        "task_response", "coherence_cohesion", "lexical_resource", "grammatical_range_accuracy")
}, "coaching_feedback": {"summary": SECRET}}


def response(content, usage=None):
    # Actual pinned SDK schema, not a guessed dictionary wrapper.
    return ChatCompletion(
        id=SECRET, object="chat.completion", created=0, model=SECRET,
        choices=[{"index": 0, "finish_reason": "stop",
                  "message": {"role": "assistant", "content": content}}],
        usage=usage,
    )


def fake_provider(monkeypatch, responses):
    pending = iter(responses)
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        item = next(pending)
        if isinstance(item, Exception):
            raise item
        return item
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    return calls


def grade(grader):
    return grader.grade(("synthetic " * 260) + SECRET, {"topic": SECRET})


def test_usage_retry_and_stages_preserve_actual_grader(monkeypatch):
    payloads = [
        response("", {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8,
                      "completion_tokens_details": {"reasoning_tokens": 2},
                      "prompt_tokens_details": {"cached_tokens": 1}}),
        response(json.dumps(SCORING)),
        response('{"annotations": []}'),
    ]
    calls = fake_provider(monkeypatch, payloads)
    grader = WritingGrader()
    original_score = grader._score_essay
    ticks = iter(range(30))
    with observe_calibration(grader, clock=lambda: next(ticks)) as events:
        result = grade(grader)
    assert result["annotation_status"] == "complete"
    assert result["coaching_feedback"]["summary"] == SECRET
    assert grader._score_essay == original_score
    assert len(calls) == 3
    attempts = [e for e in events if e["kind"] == "attempt"]
    assert [(e["stage"], e["attempt"], e["outcome"]) for e in attempts] == [
        ("scoring", 1, "empty_response"), ("scoring", 2, "response"), ("annotation", 1, "response")]
    assert attempts[0]["usage"] == dict(prompt_tokens=5, completion_tokens=3, total_tokens=8,
                                       cached_prompt_tokens=1, reasoning_tokens=2)
    assert all(v is None for v in attempts[1]["usage"].values())
    assert all(e["elapsed_ms"] >= 0 for e in events)
    assert SECRET not in json.dumps(events)
    assert [e["outcome"] for e in events if e["kind"] == "stage"] == ["success", "success"]


@pytest.mark.parametrize("failure", [RuntimeError(SECRET), response("not-json-" + SECRET)])
def test_annotation_failures_observed_but_scoring_preserved(monkeypatch, failure):
    fake_provider(monkeypatch, [response(json.dumps(SCORING)), failure])
    grader = WritingGrader()
    with observe_calibration(grader) as events:
        result = grade(grader)
    assert result["annotation_status"] == "unavailable"
    assert events[-1]["stage"] == "annotation" and events[-1]["outcome"] == "error"
    assert SECRET not in json.dumps(events)


@pytest.mark.parametrize("failure", [RuntimeError(SECRET), response("invalid-" + SECRET)])
def test_scoring_failure_retains_events_and_rethrows(monkeypatch, failure):
    calls = fake_provider(monkeypatch, [failure])
    grader = WritingGrader()
    original = grader._score_essay
    with pytest.raises((RuntimeError, ValueError)):
        with observe_calibration(grader) as events:
            grade(grader)
    assert grader._score_essay == original
    assert len(calls) == 1
    assert events[-1]["stage"] == "scoring" and events[-1]["outcome"] == "error"
    assert SECRET not in json.dumps(events)


def test_unknown_is_not_zero_and_zero_is_known():
    assert all(v is None for v in _usage(None).values())
    invalid = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=True, total_tokens=-1, completion_tokens="5"))
    assert all(v is None for v in _usage(invalid).values())
    assert _usage(response("x", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}))["total_tokens"] == 0


def test_without_observer_no_telemetry_and_identical_result(monkeypatch):
    payloads = [response(json.dumps(SCORING)), response('{"annotations": []}')]
    calls = fake_provider(monkeypatch, payloads * 2)
    grader = WritingGrader()
    plain = grade(grader)
    with observe_calibration(grader) as events:
        observed = grade(grader)
    assert plain == observed
    assert len(calls) == 4
    assert len([e for e in events if e["kind"] == "attempt"]) == 2


def test_two_empty_attempts_fail_without_annotation(monkeypatch):
    fake_provider(monkeypatch, [response(""), response("")])
    grader = WritingGrader()
    with pytest.raises(llm.EmptyCompletionError):
        with observe_calibration(grader) as events:
            grade(grader)
    assert [e["attempt"] for e in events if e["kind"] == "attempt"] == [1, 2]
    assert events[-1]["outcome"] == "error"
    assert all(e["stage"] == "scoring" for e in events)


def test_annotation_unavailable_is_distinct_from_exception(monkeypatch):
    fake_provider(monkeypatch, [response(json.dumps(SCORING)), response('{"annotations": [{"original_text": "not present", "category": "grammar", "suggestion": "synthetic", "severity": "major", "start_char": 0, "end_char": 3}]}')])
    grader = WritingGrader()
    with observe_calibration(grader) as events:
        result = grade(grader)
    assert result["annotation_status"] == "unavailable"
    assert events[-1]["outcome"] == "success"
    assert events[-1]["annotation_status"] == "unavailable"


@pytest.mark.parametrize("flag", [None, "0", "1"])
def test_calibration_harness_opt_in_only(monkeypatch, capsys, flag):
    from tests import test_calibration as harness
    if flag is None:
        monkeypatch.delenv("CALIBRATION_OBSERVE", raising=False)
    else:
        monkeypatch.setenv("CALIBRATION_OBSERVE", flag)
    fake_provider(monkeypatch, [response(json.dumps(SCORING)), response('{"annotations": []}')] * 3)
    harness.test_band_is_accurate_and_stable({
        "name": "synthetic", "essay": "synthetic " * 260, "prompt": {}, "expected_band": 6.5,
    })
    output = capsys.readouterr().out
    assert ('"events"' in output) == (flag == "1")
    assert SECRET not in output
