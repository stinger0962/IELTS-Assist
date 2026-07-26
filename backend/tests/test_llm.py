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
    assert kwargs["max_completion_tokens"] == 2000 + 1024  # visible budget + reasoning headroom
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["reasoning_effort"] == "low"


def test_reasoning_headroom_scales_with_effort():
    def budget(effort):
        return build_request(
            model="gpt-5.6-luna", messages=[], max_output_tokens=500, reasoning_effort=effort
        )["max_completion_tokens"]

    # A small visible budget must not be swallowed by reasoning tokens.
    assert budget("low") == 500 + 1024
    assert budget("medium") == 500 + 3072
    assert budget("high") == 500 + 8192
    assert budget(None) == 500 + 1024  # default headroom when effort is unset


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
