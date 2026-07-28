import pytest

from app.services.ai.llm import build_request, resolve_model


def test_next_gen_uses_max_completion_tokens_and_drops_temperature():
    kwargs = build_request(
        model="gpt-5.6-luna",
        messages=[{"role": "user", "content": "hi"}],
        max_output_tokens=2000,
        temperature=0,
        reasoning_effort="low",
    )
    assert kwargs["max_completion_tokens"] == 2000 + 8192  # visible budget + reasoning headroom
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["reasoning_effort"] == "low"


def test_reasoning_headroom_scales_with_effort():
    def budget(effort):
        return build_request(
            model="gpt-5.6-luna", messages=[], max_output_tokens=500, reasoning_effort=effort
        )["max_completion_tokens"]

    # A small visible budget must not be swallowed by reasoning tokens. Measured:
    # the annotation call alone burns ~2,700 reasoning tokens before emitting text,
    # so headroom is set ~3x above that to keep normal workflows clear of the cap.
    assert budget("low") == 500 + 8192
    assert budget("medium") == 500 + 16384
    assert budget("high") == 500 + 32768
    assert budget(None) == 500 + 8192  # default headroom when effort is unset


def test_legacy_model_gets_no_reasoning_headroom():
    kwargs = build_request(
        model="gpt-4o", messages=[], max_output_tokens=500, reasoning_effort="high"
    )
    assert kwargs["max_tokens"] == 500


def test_legacy_model_keeps_max_tokens_and_temperature():
    kwargs = build_request(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        max_output_tokens=500,
        temperature=0.7,
    )
    assert kwargs["max_tokens"] == 500
    assert kwargs["temperature"] == 0.7
    assert "max_completion_tokens" not in kwargs
    assert "reasoning_effort" not in kwargs


def test_json_mode_sets_response_format():
    kwargs = build_request(
        model="gpt-5.6-luna", messages=[], max_output_tokens=10, json_mode=True
    )
    assert kwargs["response_format"] == {"type": "json_object"}


def test_json_mode_can_be_disabled():
    kwargs = build_request(
        model="gpt-5.6-luna", messages=[], max_output_tokens=10, json_mode=False
    )
    assert "response_format" not in kwargs


def test_resolve_model_maps_tiers(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "OPENAI_MODEL_GRADER", "model-a")
    monkeypatch.setattr(settings, "OPENAI_MODEL_GENERATOR", "model-b")
    monkeypatch.setattr(settings, "OPENAI_MODEL_UTILITY", "model-c")
    assert resolve_model("grader") == "model-a"
    assert resolve_model("generator") == "model-b"
    assert resolve_model("utility") == "model-c"


def test_resolve_model_rejects_unknown_tier():
    with pytest.raises(ValueError, match="Unknown model tier"):
        resolve_model("nonsense")


def test_diversity_seed_returns_a_known_angle():
    from app.services.ai.llm import DIVERSITY_ANGLES, diversity_seed

    assert diversity_seed() in DIVERSITY_ANGLES


def test_empty_content_raises_a_diagnostic_error(monkeypatch):
    """Regression: a length-truncated response used to surface as an opaque
    json.loads failure. It must name the cause instead."""
    import app.services.ai.llm as llm

    class _Msg:
        content = ""

    class _Choice:
        message = _Msg()
        finish_reason = "length"

    class _Resp:
        choices = [_Choice()]

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    return _Resp()

    monkeypatch.setattr(llm, "get_client", lambda: _Client())
    with pytest.raises(llm.EmptyCompletionError, match="finish_reason='length'"):
        llm.chat_json(tier="grader", messages=[], max_output_tokens=100)


def test_empty_completion_is_retried_once(monkeypatch):
    """~9% of gradings died because the model spent its whole budget reasoning.
    One retry with a bigger budget and less reasoning should recover it."""
    import app.services.ai.llm as llm

    calls = []

    def _resp(content, finish):
        class _M: pass
        m = _M(); m.content = content
        class _C: pass
        c = _C(); c.message = m; c.finish_reason = finish
        class _R: pass
        r = _R(); r.choices = [c]
        return r

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    # first attempt burns its budget, second succeeds
                    return _resp("", "length") if len(calls) == 1 else _resp('{"ok":1}', "stop")

    monkeypatch.setattr(llm, "get_client", lambda: _Client())
    out = llm.chat_json(tier="grader", messages=[], max_output_tokens=2000,
                        reasoning_effort="medium")

    assert out == '{"ok":1}'
    assert len(calls) == 2, "should have retried exactly once"
    # The retry must not repeat the conditions that failed. It lowers reasoning
    # effort (the thing that ate the budget) and doubles the visible-output
    # budget. Note the TOTAL cap legitimately shrinks: dropping medium->low
    # removes far more headroom than doubling the output budget adds, and that
    # is the point — `low` reasons in the low thousands, leaving more room for
    # actual output than the 16k+ that failed.
    assert calls[1].get("reasoning_effort") == "low"
    visible = lambda k: k["max_completion_tokens"] - llm._REASONING_HEADROOM[k["reasoning_effort"]]
    assert visible(calls[1]) > visible(calls[0])


def test_gives_up_after_the_retry(monkeypatch):
    import app.services.ai.llm as llm

    calls = []

    class _Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    class _M: pass
                    m = _M(); m.content = ""
                    class _C: pass
                    c = _C(); c.message = m; c.finish_reason = "length"
                    class _R: pass
                    r = _R(); r.choices = [c]
                    return r

    monkeypatch.setattr(llm, "get_client", lambda: _Client())
    with pytest.raises(llm.EmptyCompletionError):
        llm.chat_json(tier="grader", messages=[], max_output_tokens=100)
    assert len(calls) == 2
