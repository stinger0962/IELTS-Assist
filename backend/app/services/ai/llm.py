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


# GPT-5 models bill reasoning tokens against max_completion_tokens. A budget sized
# for visible output alone gets swallowed entirely by reasoning, and the response
# comes back finish_reason="length" with EMPTY content — measured on the writing
# annotation call, which burned 2,737 reasoning tokens before writing anything.
#
# These are deliberately generous: max_completion_tokens is a cap, not a
# reservation, so unused headroom costs nothing. Callers keep specifying only the
# visible-output budget they need.
_REASONING_HEADROOM = {"minimal": 1024, "low": 4096, "medium": 8192, "high": 16384}
_DEFAULT_HEADROOM = 4096


class EmptyCompletionError(RuntimeError):
    """The model spent its whole budget reasoning and returned no content."""


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
        headroom = _REASONING_HEADROOM.get(reasoning_effort, _DEFAULT_HEADROOM)
        kwargs["max_completion_tokens"] = max_output_tokens + headroom
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
    json_mode: bool = True,
) -> str:
    """Run a completion for the given tier. Returns raw message content.

    Pass `json_mode=False` when the prompt asks for a bare JSON *array* —
    response_format=json_object requires a top-level object and would break
    callers that parse a list.
    """
    kwargs = build_request(
        model=resolve_model(tier),
        messages=messages,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
        json_mode=json_mode,
    )
    response = get_client().chat.completions.create(**kwargs)
    choice = response.choices[0]
    content = choice.message.content

    # Fail loudly. Otherwise this surfaces downstream as an opaque
    # "Expecting value: line 1 column 1 (char 0)" from json.loads.
    if not content:
        raise EmptyCompletionError(
            f"{kwargs['model']} returned empty content "
            f"(finish_reason={choice.finish_reason!r}, "
            f"cap={kwargs.get('max_completion_tokens') or kwargs.get('max_tokens')}). "
            "Raise max_output_tokens or lower reasoning_effort."
        )
    return content
