# OpenAI Model Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all OpenAI calls from the GPT-4o generation to the GPT-5.x generation, centralising model selection into config, without increasing per-user cost as the product goes live.

**Architecture:** Introduce one shared LLM helper (`backend/app/services/ai/llm.py`) that owns the OpenAI client, resolves a *tier name* → concrete model, and normalises the API parameter differences between model generations. Every existing call site stops hardcoding a model and calls the helper instead. Grading quality is protected by a calibration harness that scores a fixed essay set before and after the swap.

**Tech Stack:** Python 3, FastAPI, `openai` 2.24.0, pytest.

---

## 1. Why this migration

`gpt-4o` and `gpt-4o-mini` are **not deprecated and have no announced shutdown date** — nothing is broken today. This migration is about three things, in priority order:

1. **Grading quality.** IELTS band scoring is rubric-adherence + reasoning. This is where the GPT-5 generation is meaningfully better than GPT-4o, and grading accuracy *is* the product.
2. **Cost at launch.** `gpt-5.6-luna` ($1/$6 per 1M) is cheaper than the `gpt-4o` ($2.50/$10) it replaces, on both input and output.
3. **JSON reliability.** `CLAUDE.md` documents fragile nested formats (`groups` vs flat; matching `stems`/`options`/`answers`). Newer models plus Structured Outputs make malformed generations far rarer.

## 2. Model selection and rationale

### The tier question: do we need the top tier?

**No. `gpt-5.6-luna` is the right default; `sol` is not worth 5× the cost here.**

The `gpt-5.6` family has three tiers:

| Tier | Price /1M (in → out) | Verdict for this product |
|---|---|---|
| `gpt-5.6-sol` | $5.00 → $30.00 | ❌ Overkill. Frontier reasoning is wasted on rubric application. |
| `gpt-5.6-terra` | $2.50 → $15.00 | ➖ Fallback if calibration shows luna under-performs. |
| `gpt-5.6-luna` | $1.00 → $6.00 | ✅ **Default.** Cheaper than today's gpt-4o, far more capable. |

Grading an essay against published band descriptors is *bounded* reasoning: the rubric is supplied in the prompt, the output is four numbers plus evidence quotes. What matters is **consistency** (same essay → same band) and **calibration** (bands match a real examiner). Those come from reasoning discipline, prompt anchoring and low variance — not from frontier model capacity. Paying 5× for `sol` buys capability this task does not consume.

⚠️ **This is a hypothesis, not a fact.** Task 7 builds a calibration harness to test it empirically before we commit. If luna under-scores or over-scores against known bands, we escalate to `terra`, changing one config value.

### Cost model (per graded essay)

Writing grading = 2 calls: scoring (~4,900 in / ~800 out) + annotation (~1,100 in / ~700 out). Assume ~1,000 extra reasoning tokens billed as output.

| Model | In | Out (incl. reasoning) | **Per essay** | 400 essays/mo |
|---|---|---|---|---|
| `gpt-4o` (today) | ~$0.015 | ~$0.015 | **$0.030** | $12.00 |
| **`gpt-5.6-luna`** | ~$0.006 | ~$0.015 | **$0.021** | **$8.40** |
| `gpt-5.6-luna` + caching | ~$0.002 | ~$0.015 | **$0.017** | **$6.80** |
| `gpt-5.6-sol` | ~$0.030 | ~$0.075 | $0.105 | $42.00 |

**Migrating to luna reduces grading cost ~30% versus today**, and ~45% once prompt caching is on (Task 8). At 100 active students the entire OpenAI bill lands near **$15–25/month**.

### Final tier assignments

| Tier name | Model | Used by |
|---|---|---|
| `grader` | `gpt-5.6-luna` | `writing_grader.py`, `speaking_grader.py` |
| `generator` | `gpt-5.6-luna` | `practice_generator.py`, `listening_generator.py`, `grammar_generator.py` |
| `utility` | `gpt-5.4-nano` | `routers/generate.py` (mistake explain, vocab extract) |

Confirmed available on the production account: the full `gpt-5`, `gpt-5.1`–`gpt-5.4` families including `gpt-5.4-mini` and `gpt-5.4-nano`. **`gpt-5.5`/`gpt-5.6` availability is unverified** — Task 0 confirms it and falls back to `gpt-5.4` (grader/generator) if absent.

## 3. Two breaking API changes

These will cause hard failures if missed. Both are handled centrally in `llm.py`.

1. **`max_tokens` is rejected** by GPT-5 models — it becomes `max_completion_tokens`. Affects all 10 call sites.
2. **`temperature` is rejected** (only the default is accepted). Affects every call site, which currently span `temperature=0` → `0.85`.

⚠️ **Consequence for content generation.** The generators deliberately use `temperature=0.85` to make passages varied rather than repetitive. Removing temperature removes that diversity lever. The replacement is **prompt-level diversity seeding** — injecting an explicit varying angle per request (Task 5). `listening_generator.py` already does something similar with `avoid_domains`, so this extends an established pattern rather than inventing one.

## 4. File structure

| File | Responsibility |
|---|---|
| `backend/app/services/ai/llm.py` | **Create.** Shared client, tier→model resolution, parameter normalisation. |
| `backend/app/config.py` | **Modify.** Replace single `OPENAI_MODEL` with three tier settings. |
| `backend/app/services/ai/writing_grader.py` | **Modify.** 2 call sites, drop hardcoded model. |
| `backend/app/services/ai/speaking_grader.py` | **Modify.** 1 call site. |
| `backend/app/services/ai/practice_generator.py` | **Modify.** 3 call sites + diversity seed. |
| `backend/app/services/ai/listening_generator.py` | **Modify.** 3 call sites + diversity seed. |
| `backend/app/services/ai/grammar_generator.py` | **Modify.** 2 call sites. |
| `backend/app/routers/generate.py` | **Modify.** 2 inline call sites. |
| `backend/tests/test_llm.py` | **Create.** Unit tests for parameter normalisation. |
| `backend/tests/test_calibration.py` | **Create.** Grading calibration harness (opt-in, network). |

---

## Task 0: Compatibility spike (no code committed)

**Purpose:** Verify assumptions before writing code. This task exists because tier availability and parameter rejection were *not* verifiable during planning.

**Files:** none — throwaway script.

- [ ] **Step 1: Confirm which tiers the production account can see**

On the VPS (read-only, free API call):

```bash
cd /root/IELTS-Assist/backend && source venv/bin/activate && python3 -c "
from openai import OpenAI; import os
ids = sorted(m.id for m in OpenAI(api_key=os.environ['OPENAI_API_KEY']).models.list().data)
for t in ('gpt-5.6','gpt-5.5','gpt-5.4'):
    print(t, [i for i in ids if i.startswith(t)] or 'NOT AVAILABLE')
"
```

Expected: a list of available model ids per family.

**Decision rule:** if `gpt-5.6-luna` is absent, use `gpt-5.4` for `grader`/`generator` everywhere below.

- [ ] **Step 2: Confirm `temperature` and `max_tokens` are rejected**

```bash
cd /root/IELTS-Assist/backend && source venv/bin/activate && python3 -c "
from openai import OpenAI; import os
c = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
for kw in ({'temperature':0}, {'max_tokens':50}):
    try:
        c.chat.completions.create(model='gpt-5.4', messages=[{'role':'user','content':'hi'}], **kw)
        print(kw, '-> ACCEPTED')
    except Exception as e:
        print(kw, '-> REJECTED:', str(e)[:120])
"
```

Expected: both `REJECTED`. If either is *accepted*, note it — the helper in Task 2 still works, but the constraint is looser than assumed.

- [ ] **Step 3: Record findings**

Write the confirmed tier names and parameter behaviour into this plan's Section 2 table before proceeding. No commit.

---

## Task 1: Centralise model configuration

**Files:**
- Modify: `backend/app/config.py:20-22`

- [ ] **Step 1: Replace the single model setting with three tiers**

In `backend/app/config.py`, replace:

```python
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
```

with:

```python
    # OpenAI
    OPENAI_API_KEY: str = ""
    # Model tiers — override per environment without touching code.
    # grader:    band scoring (quality-critical, per-user cost)
    # generator: content authoring (quality matters, cost amortised across users)
    # utility:   short mechanical calls (cheapest tier)
    OPENAI_MODEL_GRADER: str = "gpt-5.6-luna"
    OPENAI_MODEL_GENERATOR: str = "gpt-5.6-luna"
    OPENAI_MODEL_UTILITY: str = "gpt-5.4-nano"
```

If Task 0 showed `gpt-5.6-luna` is unavailable, use `"gpt-5.4"` for the first two values.

- [ ] **Step 2: Verify config loads**

Run: `cd backend && python -c "from app.config import settings; print(settings.OPENAI_MODEL_GRADER, settings.OPENAI_MODEL_GENERATOR, settings.OPENAI_MODEL_UTILITY)"`
Expected: `gpt-5.6-luna gpt-5.6-luna gpt-5.4-nano`

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(ai): replace single OPENAI_MODEL with grader/generator/utility tiers"
```

---

## Task 2: Shared LLM helper

The DRY core. Every call site routes through this, so a future model change is one config edit.

**Files:**
- Create: `backend/app/services/ai/llm.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_llm.py`:

```python
from app.services.ai.llm import build_request, resolve_model


def test_next_gen_uses_max_completion_tokens_and_drops_temperature():
    kwargs = build_request(
        model="gpt-5.6-luna",
        messages=[{"role": "user", "content": "hi"}],
        max_output_tokens=2000,
        temperature=0,
        reasoning_effort="low",
    )
    assert kwargs["max_completion_tokens"] == 2000
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["reasoning_effort"] == "low"


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
        model="gpt-5.6-luna",
        messages=[],
        max_output_tokens=10,
        json_mode=True,
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
    import pytest

    with pytest.raises(ValueError):
        resolve_model("nonsense")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.ai.llm'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/services/ai/llm.py`:

```python
"""Central OpenAI access: one client, tier-based model selection, parameter normalisation.

Why this exists:
- The model name must live in config, not scattered across call sites.
- GPT-5-generation models reject `max_tokens` (use `max_completion_tokens`) and
  reject `temperature`. Older models reject `reasoning_effort`. Normalising here
  keeps every call site free of generation-specific branching.
"""

from openai import OpenAI

from app.config import settings

_TIERS = {
    "grader": "OPENAI_MODEL_GRADER",
    "generator": "OPENAI_MODEL_GENERATOR",
    "utility": "OPENAI_MODEL_UTILITY",
}

_client = None


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
    """Build chat.completions kwargs valid for the given model generation."""
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
    model = resolve_model(tier)
    kwargs = build_request(
        model=model,
        messages=messages,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )
    response = get_client().chat.completions.create(**kwargs)
    return response.choices[0].message.content
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_llm.py -v`
Expected: PASS — 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/llm.py backend/tests/test_llm.py
git commit -m "feat(ai): add shared LLM helper with tier resolution and param normalisation"
```

---

## Task 3: Migrate the writing grader

**Files:**
- Modify: `backend/app/services/ai/writing_grader.py:310-334`, `:359-368`, `:432-441`

- [ ] **Step 1: Replace the client and model attributes**

In `backend/app/services/ai/writing_grader.py`, replace the import:

```python
from openai import OpenAI
from app.config import settings
```

with:

```python
from app.services.ai.llm import chat_json, resolve_model
```

Then replace the `__init__` body (currently lines 315-317):

```python
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o"
```

with:

```python
    def __init__(self):
        self.model = resolve_model("grader")
```

`self.model` is retained because `grade()` records it in the result payload (`result["model"]`), which the frontend displays.

- [ ] **Step 2: Replace the scoring call**

Replace lines 359-370 (the `self.client.chat.completions.create(...)` block through `raw = response.choices[0].message.content`) with:

```python
        raw = chat_json(
            tier="grader",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=2000,
            temperature=0,
            reasoning_effort="medium",
        )
```

`reasoning_effort="medium"` is the deliberate choice for scoring: enough deliberation to apply the rubric consistently, without paying for `high`.

- [ ] **Step 3: Replace the annotation call**

Replace lines 432-443 (the second `create(...)` block through `raw = response.choices[0].message.content`) with:

```python
        raw = chat_json(
            tier="grader",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=1500,
            temperature=0.2,
            reasoning_effort="low",
        )
```

- [ ] **Step 4: Update the module docstring**

Replace lines 3 and 14 which name the old model:

```python
Layer A+B: Holistic scoring with soft penalties (1 GPT-4o call, temperature=0)
```
→
```python
Layer A+B: Holistic scoring with soft penalties (1 grader-tier call, reasoning_effort=medium)
```

```python
Layer C: Learner annotations (1 GPT-4o call, temperature=0.2)
```
→
```python
Layer C: Learner annotations (1 grader-tier call, reasoning_effort=low)
```

Also update the class docstring on line 311 from `using GPT-4o (v2.0)` to `using the configured grader tier (v2.0)`.

- [ ] **Step 5: Verify no stale references remain**

Run: `cd backend && grep -n "gpt-4o\|self.client\|OpenAI(" app/services/ai/writing_grader.py`
Expected: no output.

- [ ] **Step 6: Run the test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS — no regressions.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai/writing_grader.py
git commit -m "feat(ai): migrate writing grader to configured grader tier"
```

---

## Task 4: Migrate the speaking grader

**Files:**
- Modify: `backend/app/services/ai/speaking_grader.py:77-83`, `:114-121`
- Test: `backend/tests/test_speaking_grader.py` (existing)

- [ ] **Step 1: Replace client construction**

Apply the same import change as Task 3 Step 1, then replace the `self.client = OpenAI(...)` / `self.model = "gpt-4o"` pair in `__init__` (around line 83) with:

```python
        self.model = resolve_model("grader")
```

- [ ] **Step 2: Replace the grading call**

Replace the `create(...)` block at lines 114-121 and the line that reads `response.choices[0].message.content` with:

```python
        raw = chat_json(
            tier="grader",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=2000,
            temperature=0,
            reasoning_effort="medium",
        )
```

Keep the existing variable name used downstream — if the current code assigns to something other than `raw`, rename the assignment above to match rather than editing the parsing code.

- [ ] **Step 3: Update the docstrings naming GPT-4o**

Line 5 (`Layer 3: GPT-4o grades FC, LR, GRA...`) and line 77 (`using Azure PA + GPT-4o`): replace `GPT-4o` with `the grader tier`.

- [ ] **Step 4: Run the existing speaking grader test**

Run: `cd backend && python -m pytest tests/test_speaking_grader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/speaking_grader.py
git commit -m "feat(ai): migrate speaking grader to configured grader tier"
```

---

## Task 5: Migrate the content generators

Three files, eight call sites, plus the diversity replacement for lost `temperature`.

**Files:**
- Modify: `backend/app/services/ai/practice_generator.py:210`, `:289-297`, `:331`, `:349`
- Modify: `backend/app/services/ai/listening_generator.py:239`, `:333-341`, `:366-374`, `:415-423`
- Modify: `backend/app/services/ai/grammar_generator.py:194`, `:290-298`, `:307-315`

- [ ] **Step 1: Add a diversity seed helper**

Append to `backend/app/services/ai/llm.py`:

```python
# Diversity angles — replaces the variety previously produced by temperature=0.85.
# The caller picks one at random per generation so repeated requests differ.
DIVERSITY_ANGLES = [
    "Take an unexpected angle on the topic that most writers would overlook.",
    "Ground the piece in a specific real-world case or setting.",
    "Foreground a tension or trade-off rather than a straightforward description.",
    "Use a historical or comparative framing.",
    "Centre the piece on a process or mechanism rather than opinions.",
    "Approach the topic through its measurable effects and data.",
]


def diversity_seed() -> str:
    """Return one diversity instruction. Call per generation request."""
    import random

    return random.choice(DIVERSITY_ANGLES)
```

- [ ] **Step 2: Migrate each generator's `__init__`**

In all three generator files, replace `self.model = "gpt-4o-mini"` with:

```python
        self.model = resolve_model("generator")
```

and replace the `OpenAI(...)` client construction and its import with `from app.services.ai.llm import chat_json, resolve_model, diversity_seed`.

- [ ] **Step 3: Migrate each generation call site**

For each of the eight `self.client.chat.completions.create(...)` blocks, replace with a `chat_json(...)` call preserving the existing `max_tokens` value as `max_output_tokens` and the existing `temperature` value, and adding `reasoning_effort`:

- Creative authoring calls (those currently at `temperature=0.85`, i.e. `practice_generator.py:289`, `listening_generator.py:333`): use `reasoning_effort="low"` and append the diversity seed to the system message:

```python
            raw = chat_json(
                tier="generator",
                messages=[
                    {"role": "system", "content": system_msg + "\n\n" + diversity_seed()},
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=3500,
                temperature=0.85,
                reasoning_effort="low",
            )
```

- Question-writing calls (`temperature=0.5`, `listening_generator.py:366`; `temperature=0.7`, `grammar_generator.py:290`): use `reasoning_effort="medium"`, no diversity seed, preserving each site's own `max_tokens` value.
- Validation calls (`temperature=0.3`, `max_tokens=500` — `listening_generator.py:415`, `grammar_generator.py:307`): use `reasoning_effort="low"`.

Then replace each `self._parse_json(response.choices[0].message.content)` with `self._parse_json(raw)`.

- [ ] **Step 4: Verify no stale references remain**

Run: `cd backend && grep -rn "gpt-4o\|self.client\|OpenAI(" app/services/ai/practice_generator.py app/services/ai/listening_generator.py app/services/ai/grammar_generator.py`
Expected: no output.

- [ ] **Step 5: Run the test suite**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai/practice_generator.py backend/app/services/ai/listening_generator.py backend/app/services/ai/grammar_generator.py backend/app/services/ai/llm.py
git commit -m "feat(ai): migrate content generators to generator tier with prompt-level diversity"
```

---

## Task 6: Migrate the inline router calls

**Files:**
- Modify: `backend/app/routers/generate.py:259-265`, `:341-347`
- Test: `backend/tests/test_generate.py` (existing)

- [ ] **Step 1: Replace the mistake-explanation call**

Replace lines 259-265:

```python
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
```

with:

```python
        raw = chat_json(
            tier="utility",
            messages=[{"role": "user", "content": prompt}],
            max_output_tokens=1500,
            temperature=0.2,
            reasoning_effort="low",
        ).strip()
```

⚠️ These two call sites currently pass no `max_tokens` at all. Setting an explicit bound is required, because GPT-5 models spend reasoning tokens and an unbounded call can truncate mid-JSON.

- [ ] **Step 2: Replace the vocabulary-extraction call**

Replace lines 341-347 with the same shape, using `max_output_tokens=1500` and `temperature=0.3`.

- [ ] **Step 3: Add the import**

At the top of `backend/app/routers/generate.py`, add:

```python
from app.services.ai.llm import chat_json
```

and remove the now-unused `from openai import OpenAI` if no other call site in the file needs it.

- [ ] **Step 4: Verify**

Run: `cd backend && grep -n "gpt-4o\|OpenAI(" app/routers/generate.py`
Expected: no output.

Run: `cd backend && python -m pytest tests/test_generate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/generate.py
git commit -m "feat(ai): migrate inline router calls to utility tier"
```

---

## Task 7: Grading calibration harness

**This is the task that de-risks the whole migration.** Without it we are guessing that luna grades as well as gpt-4o.

**Files:**
- Create: `backend/tests/test_calibration.py`

- [ ] **Step 1: Write the harness**

Create `backend/tests/test_calibration.py`:

```python
"""Grading calibration harness.

Not part of the default suite — it makes real API calls and costs money.
Run explicitly:  pytest tests/test_calibration.py -m calibration -s

Purpose: confirm a model change does not shift band scores. Add essays with
known/expected bands to ESSAYS below; the more anchors, the better the signal.
"""

import statistics

import pytest

from app.services.ai.writing_grader import WritingGrader

pytestmark = pytest.mark.calibration

PROMPT = {
    "essay_type": "opinion",
    "statement": "Some people believe that unpaid community service should be a compulsory part of high school programmes.",
    "instruction": "To what extent do you agree or disagree?",
}

# Replace the placeholder text with real essays whose bands you trust.
ESSAYS = [
    {"name": "band6_sample", "expected": 6.0, "text": "<paste a real band-6 essay here>"},
    {"name": "band7_sample", "expected": 7.0, "text": "<paste a real band-7 essay here>"},
]

RUNS_PER_ESSAY = 3
TOLERANCE = 0.5


@pytest.mark.parametrize("sample", ESSAYS, ids=lambda s: s["name"])
def test_band_is_accurate_and_stable(sample):
    grader = WritingGrader()
    bands = []
    for _ in range(RUNS_PER_ESSAY):
        result = grader.grade(sample["text"], PROMPT)
        bands.append(result["examiner_result"]["overall_band"])

    mean = statistics.mean(bands)
    spread = max(bands) - min(bands)
    print(f"\n{sample['name']}: bands={bands} mean={mean} spread={spread} model={grader.model}")

    assert spread <= TOLERANCE, f"Unstable grading: {bands} (spread {spread} > {TOLERANCE})"
    assert abs(mean - sample["expected"]) <= TOLERANCE, (
        f"Miscalibrated: mean {mean} vs expected {sample['expected']}"
    )
```

- [ ] **Step 2: Register the marker**

Create `backend/pytest.ini` (or add to it if it exists):

```ini
[pytest]
markers =
    calibration: makes real OpenAI API calls and costs money; not run by default
addopts = -m "not calibration"
```

- [ ] **Step 3: Confirm the default suite still excludes it**

Run: `cd backend && python -m pytest tests/ -v`
Expected: PASS, with the calibration tests **deselected**.

- [ ] **Step 4: Capture a baseline before switching models**

Temporarily set `OPENAI_MODEL_GRADER=gpt-4o` and run:

```bash
cd backend && OPENAI_MODEL_GRADER=gpt-4o python -m pytest tests/test_calibration.py -m calibration -s
```

Record the printed bands — this is the old-model baseline.

- [ ] **Step 5: Compare against the new model**

```bash
cd backend && python -m pytest tests/test_calibration.py -m calibration -s
```

**Decision rule:** if bands stay within ±0.5 of both the expected value and the gpt-4o baseline, luna is confirmed. If they drift, set `OPENAI_MODEL_GRADER=gpt-5.6-terra` and re-run before considering `sol`.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_calibration.py backend/pytest.ini
git commit -m "test(ai): add opt-in grading calibration harness"
```

---

## Task 8: Prompt caching for the graders

The writing grader's system prompt (band descriptors + calibration + task-type rules) is ~4,500 tokens and **identical on every call**. Cached input bills at 10% of standard input.

**Files:**
- Modify: `backend/app/services/ai/writing_grader.py` (message assembly in `_score_essay`)

- [ ] **Step 1: Put the static content first and the variable content last**

Caching keys on a common prefix, so the prompt must begin with the invariant text. In `_score_essay`, `SCORING_SYSTEM_PROMPT.format(...)` interpolates `task_completion_instructions`, which **varies by essay type** and currently sits in the middle — breaking the cacheable prefix for every type.

Restructure into two system messages so the invariant block is a stable prefix:

```python
        static_prefix = SCORING_SYSTEM_PROMPT_HEAD.format(
            band_descriptors=BAND_DESCRIPTORS,
            scoring_calibration=SCORING_CALIBRATION,
        )
        raw = chat_json(
            tier="grader",
            messages=[
                {"role": "system", "content": static_prefix},
                {"role": "system", "content": task_instructions},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=2000,
            temperature=0,
            reasoning_effort="medium",
        )
```

This requires splitting `SCORING_SYSTEM_PROMPT` into `SCORING_SYSTEM_PROMPT_HEAD` (everything except `{task_completion_instructions}`, keeping the output-format section) — a pure text refactor with no behaviour change.

- [ ] **Step 2: Re-run calibration to prove the restructure did not move scores**

```bash
cd backend && python -m pytest tests/test_calibration.py -m calibration -s
```

Expected: bands unchanged within ±0.5 of the Task 7 result.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/ai/writing_grader.py
git commit -m "perf(ai): restructure grader prompt for cache-friendly static prefix"
```

---

## Task 9: Deploy

Per `CLAUDE.md`: **deployment happens only through GitHub Actions. Never SSH to deploy.**

- [ ] **Step 1: Push the branch and open a PR**

```bash
git push -u origin feat/openai-model-migration
```

- [ ] **Step 2: Confirm CI passes**

```bash
gh run list --workflow=ci.yml -L 3
```

Expected: the run for this branch is `success`.

- [ ] **Step 3: Merge to main and confirm the deploy workflow**

```bash
gh run list --workflow=deploy.yml -L 3
```

Expected: `success`. The deploy runs `pytest` on the VPS before restarting `ielts-backend`.

- [ ] **Step 4: Verify in production**

Grade one real essay through the UI at `https://annababy.cc` and confirm the returned payload's `model` field shows the new model id.

---

## Appendix A: The other API services

The question was whether anything besides OpenAI needs upgrading. Findings:

| Service | Used for | Verdict |
|---|---|---|
| **Google Cloud TTS** (Neural2, $16/1M chars) | Listening audio | ✅ **Keep.** Accent coverage (en-GB/AU/US/IN) is a genuine IELTS requirement Google serves well. MP3s are cached to disk and preserved across deploys, so this is a one-time cost per exercise, amortised across all users — not a per-user cost. Chirp 3 HD ($30/1M) is a quality option, not a necessity. |
| **Azure Speech** (Pronunciation Assessment, ~$1/audio hour) | Speaking pronunciation scores | ✅ **Keep.** Phoneme-level scoring has no OpenAI equivalent. ~$0.03 per 2-minute attempt. |
| **Youdao 有道智云** | Chinese translation of definitions | ➖ **Candidate for removal.** The `utility` tier can produce context-aware Chinese definitions for a fraction of a cent, retiring one vendor, one key and one failure mode. Low priority. |
| **dictionaryapi.dev** | English definitions | ⚠️ **Address before launch.** A free, unauthenticated public API with no SLA, called **directly from the browser** in three places (`AIGrammarView.tsx:80`, `useVocabSelection.ts:30`, `Topics.tsx:83`). If it rate-limits or disappears, vocabulary lookup breaks for every user. Should be proxied through the backend and cached in Postgres. |

## Appendix B: Production-readiness items (separate plan needed)

These surfaced during investigation. They are **not** part of this migration — they belong in their own plan — but they matter more than the model swap for a live launch:

1. 🔴 **No rate limiting or per-user quotas on AI endpoints.** The single largest financial risk at launch: any user (or bot) can trigger unbounded generation and grading calls. Needs per-user daily caps before public traffic.
2. 🔴 **`SECRET_KEY` defaults to `"your-secret-key-change-in-production"`** (`config.py:13`). If the environment does not override it, JWTs are forgeable. Verify the production override exists.
3. 🟠 **Backend runs uvicorn with `--reload`** (confirmed in the systemd unit). A development flag: extra memory on a 2 GB box and restarts on file change. Remove for production.
4. 🟠 **No swap on a 2 GB droplet** (~436 MB free at inspection). Add a swapfile.
5. 🟡 **`BACKEND_CORS_ORIGINS` still lists only localhost** (`config.py:18`). Works today because nginx makes it same-origin, but it is misleading and will bite if an API subdomain is ever introduced.
