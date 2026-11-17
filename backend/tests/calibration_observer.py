"""Opt-in, sequential calibration instrumentation; never imported by runtime.

Patches are process-global: do not use around concurrent application requests.
No prompts, responses, exception text, identifiers or credentials are retained.
"""
from contextlib import contextmanager
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

from app.services.ai import llm


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _usage(response):
    usage = getattr(response, "usage", None)
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    return {
        "prompt_tokens": _count(getattr(usage, "prompt_tokens", None)),
        "completion_tokens": _count(getattr(usage, "completion_tokens", None)),
        "total_tokens": _count(getattr(usage, "total_tokens", None)),
        "cached_prompt_tokens": _count(getattr(prompt_details, "cached_tokens", None)),
        "reasoning_tokens": _count(getattr(completion_details, "reasoning_tokens", None)),
    }


@contextmanager
def observe_calibration(grader, *, clock=perf_counter):
    """Yield non-content stage/attempt events; preserve return values/exceptions.

    Each attempt is one SDK create() invocation, not an SDK-internal HTTP retry.
    None means unknown, never zero usage/cost. This helper computes no money.
    Events are appended even when grading raises; caller owns local retention.
    """
    events = []
    stage = None
    attempt = 0
    original_client = llm.get_client

    def create(**kwargs):
        nonlocal attempt
        attempt += 1
        started = clock()
        response = None
        outcome = "provider_error"
        try:
            response = original_client().chat.completions.create(**kwargs)
            outcome = "response"
            choices = getattr(response, "choices", None)
            if choices and not choices[0].message.content:
                outcome = "empty_response"
            return response
        finally:
            events.append({
                "kind": "attempt", "stage": stage, "attempt": attempt,
                "outcome": outcome, "elapsed_ms": max(0, (clock() - started) * 1000),
                "usage": _usage(response),
            })

    proxy = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    def wrap(name, original):
        def run(*args, **kwargs):
            nonlocal stage, attempt
            stage, attempt = name, 0
            started = clock()
            outcome = "error"
            annotation_status = None
            try:
                result = original(*args, **kwargs)
                outcome = "success"
                if name == "annotation" and isinstance(result, tuple) and len(result) == 2:
                    if result[1] in ("complete", "partial", "unavailable"):
                        annotation_status = result[1]
                return result
            finally:
                events.append({
                    "kind": "stage", "stage": name, "outcome": outcome,
                    "elapsed_ms": max(0, (clock() - started) * 1000),
                    "annotation_status": annotation_status,
                })
                stage = None
        return run

    with patch.object(llm, "get_client", return_value=proxy), \
         patch.object(grader, "_score_essay", wrap("scoring", grader._score_essay)), \
         patch.object(grader, "_annotate_errors", wrap("annotation", grader._annotate_errors)):
        yield events
