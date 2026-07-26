"""Central OpenAI access: one client, tier-based model selection, parameter normalisation.

Why this exists:
- The model name must live in config, not scattered across call sites.
- GPT-5-generation models reject `max_tokens` (use `max_completion_tokens`) and
  reject `temperature`. Older models reject `reasoning_effort`. Normalising here
  keeps every call site free of generation-specific branching.

Verified against the production account on 2026-07-26 (gpt-5.6-luna):
  temperature=0             -> 400 Unsupported value
  max_tokens=16             -> 400 Unsupported parameter
  max_completion_tokens=16  -> accepted
"""

import random

from openai import OpenAI

from app.config import settings

_TIERS = {
    "grader": "OPENAI_MODEL_GRADER",
    "generator": "OPENAI_MODEL_GENERATOR",
    "utility": "OPENAI_MODEL_UTILITY",
}

_client = None

# Diversity angles — replaces the variety previously produced by temperature=0.85,
# which the GPT-5 generation no longer accepts. Callers pick one per generation so
# repeated requests on the same topic differ.
DIVERSITY_ANGLES = [
    "Take an unexpected angle on the topic that most writers would overlook.",
    "Ground the piece in a specific real-world case or setting.",
    "Foreground a tension or trade-off rather than a straightforward description.",
    "Use a historical or comparative framing.",
    "Centre the piece on a process or mechanism rather than opinions.",
    "Approach the topic through its measurable effects and data.",
]


def get_client() -> OpenAI:
    """Module-level client, created once."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def resolve_model(tier: str) -> str:
    """Map a tier name to the configured model id."""
    if tier not in _TIERS:
        raise ValueError(f"Unknown model tier: {tier!r}. Expected one of {sorted(_TIERS)}")
    return getattr(settings, _TIERS[tier])


def diversity_seed() -> str:
    """Return one diversity instruction. Call per generation request."""
    return random.choice(DIVERSITY_ANGLES)


def _is_next_gen(model: str) -> bool:
    """True for GPT-5-generation models, which use the newer parameter set."""
    return model.startswith("gpt-5")


def build_request(
    *,
    model: str,
    messages: list,
    max_output_tokens: int,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    json_mode: bool = True,
) -> dict:
    """Build chat.completions kwargs valid for the given model generation.

    `temperature` is accepted and ignored for next-gen models so call sites can
    keep documenting their intended determinism without branching.
    """
    kwargs: dict = {"model": model, "messages": messages}

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    if _is_next_gen(model):
        kwargs["max_completion_tokens"] = max_output_tokens
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        # temperature deliberately omitted: rejected by this generation.
    else:
        kwargs["max_tokens"] = max_output_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature

    return kwargs


def chat_json(
    *,
    tier: str,
    messages: list,
    max_output_tokens: int,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
) -> str:
    """Run a JSON-mode completion for the given tier. Returns raw message content."""
    kwargs = build_request(
        model=resolve_model(tier),
        messages=messages,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )
    response = get_client().chat.completions.create(**kwargs)
    return response.choices[0].message.content
