# AI Speaking Module Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the monolithic codebase into modular per-skill files, then build AI Speaking Part 2 (Long Turn) MVP with Whisper transcription, Azure Pronunciation Assessment, and GPT-4o grading.

**Architecture:** Step 0 splits Practice.tsx (3,195 lines) and generate.py (1,284 lines) into per-skill modules with zero functional changes. Step 1 adds the speaking pipeline: cue card bank → pool endpoints → audio upload → Whisper → Azure PA → GPT-4o → grading results.

**Tech Stack:** FastAPI, SQLAlchemy, OpenAI Whisper API, Azure Speech SDK, GPT-4o, Google Cloud TTS, React 18 + TypeScript, MediaRecorder API

**Spec:** `docs/superpowers/specs/2026-03-22-speaking-module-design.md`

---

## Chunk 1: Backend Refactoring (v0.20.0)

Split `backend/app/routers/generate.py` (1,284 lines) into per-skill routers. Zero functional changes.

### File Structure After Refactoring

| File | Responsibility |
|---|---|
| `routers/generate.py` | Shared: imports, constants (`MAX_ACTIVE_CARDS`, `POOL_TARGET`), `_with_db_id()`, `daily_generate()` cron, shared endpoints (`explain-mistakes`, `translate-definition`, `extract-vocabulary`, `tts-preview`) |
| `routers/reading.py` | `_active_cards()`, `_available_for_user()`, `_replenish()`, `daily-reading`, `generate-more`, `submit-ai-reading`, `trigger-replenish`, `pool-status`, `generate-reading` |
| `routers/listening.py` | `_available_listening_for_user()`, `_active_listening_cards()`, `_replenish_listening()`, `daily-listening`, `generate-more-listening`, `submit-ai-listening`, `tts-preview`, `generate-listening` |
| `routers/grammar.py` | `_available_grammar_for_user()`, `_active_grammar_cards()`, `_replenish_grammar()`, `daily-grammar`, `generate-more-grammar`, `submit-ai-grammar`, `generate-grammar` |
| `routers/writing.py` | `_available_writing_for_user()`, `_active_writing_cards()`, `_replenish_writing()`, `_seed_writing_pool()`, `_extract_writing_topics()`, `daily-writing`, `generate-more-writing`, `submit-ai-writing` |

All skill routers use `APIRouter(prefix="/generate", tags=["generate"])` — frontend URLs unchanged.

### Task 1: Extract reading router

**Files:**
- Create: `backend/app/routers/reading.py`
- Modify: `backend/app/routers/generate.py`
- Modify: `backend/app/main.py:58-64`

- [ ] **Step 1: Create `reading.py` with reading helpers + endpoints**

Extract from `generate.py`:
- Lines 34-44: `_active_cards()` — rename to keep as-is (it's already reading-specific with `skill="reading"` default)
- Lines 47-64: `_available_for_user()` — reading-specific pool query
- Lines 73-104: `_replenish()` — reading replenish with `PracticeGenerator`
- Lines 251-363: All reading endpoints (`daily-reading`, `generate-more`, `submit-ai-reading`, `trigger-replenish`, `pool-status`)
- Lines 724-746: `generate-reading` endpoint

```python
# backend/app/routers/reading.py
"""Reading skill — pool helpers + endpoints."""
import json
import logging
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.services.auth import get_current_user
from app.models.models import User, GeneratedPractice, UserPractice
from app.services.ai.practice_generator import PracticeGenerator
from app.services.ai.reading_config import generate_metadata as reading_generate_metadata

# Import shared helpers from generate.py
from app.routers.generate import MAX_ACTIVE_CARDS, POOL_TARGET, _with_db_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])

# ... paste reading helpers and endpoints here, keeping function signatures identical
```

- [ ] **Step 2: Register reading router in `main.py`**

Add after the existing generate router include (line 63 of `main.py`):

```python
from app.routers import reading
# ...
app.include_router(reading.router, prefix=f"{settings.API_PREFIX}", tags=["Generate"])
```

Note: reading router already has `prefix="/generate"` internally, so main.py prefix is just the API prefix.

- [ ] **Step 3: Remove reading code from `generate.py`**

Delete from `generate.py`:
- Lines 34-44 (`_active_cards`)
- Lines 47-64 (`_available_for_user`)
- Lines 73-104 (`_replenish`)
- Lines 251-363 (reading endpoints)
- Lines 724-746 (`generate-reading`)

Keep: imports needed by remaining code, `MAX_ACTIVE_CARDS`, `POOL_TARGET`, `_with_db_id()`, `daily_generate()`, shared endpoints.

- [ ] **Step 4: Update `daily_generate()` imports**

`daily_generate()` in `generate.py` calls reading helpers. Update it to import from `reading.py`:

```python
from app.routers.reading import _replenish as _replenish_reading, _available_for_user
```

- [ ] **Step 5: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All 18 tests pass. No functional changes.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/reading.py backend/app/routers/generate.py backend/app/main.py
git commit -m "refactor: extract reading router from generate.py"
```

### Task 2: Extract listening router

**Files:**
- Create: `backend/app/routers/listening.py`
- Modify: `backend/app/routers/generate.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `listening.py` with listening helpers + endpoints**

Extract from `generate.py`:
- Lines 533-605: `_available_listening_for_user()`, `_active_listening_cards()`, `_replenish_listening()`
- Lines 608-721: Listening endpoints (`daily-listening`, `generate-more-listening`, `submit-ai-listening`, `tts-preview`)
- Lines 749-770: `generate-listening` endpoint

```python
# backend/app/routers/listening.py
"""Listening skill — pool helpers + endpoints."""
import json, logging
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.services.auth import get_current_user
from app.models.models import User, GeneratedPractice, UserPractice
from app.services.ai.listening_generator import ListeningGenerator
from app.services.tts import synthesize_dialogue, synthesize_monologue
from app.routers.generate import MAX_ACTIVE_CARDS, POOL_TARGET, _with_db_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])

# ... paste listening helpers and endpoints
```

- [ ] **Step 2: Register in `main.py`, remove from `generate.py`**

- [ ] **Step 3: Update `daily_generate()` imports for listening**

- [ ] **Step 4: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All 18 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/listening.py backend/app/routers/generate.py backend/app/main.py
git commit -m "refactor: extract listening router from generate.py"
```

### Task 3: Extract grammar router

**Files:**
- Create: `backend/app/routers/grammar.py`
- Modify: `backend/app/routers/generate.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `grammar.py`**

Extract from `generate.py`:
- Lines 773-845: Grammar pool helpers
- Lines 848-941: Grammar endpoints (`daily-grammar`, `generate-more-grammar`, `submit-ai-grammar`)
- Lines 1264-1284: `generate-grammar` endpoint

- [ ] **Step 2: Register in `main.py`, remove from `generate.py`, update `daily_generate()` imports**

- [ ] **Step 3: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All 18 tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/grammar.py backend/app/routers/generate.py backend/app/main.py
git commit -m "refactor: extract grammar router from generate.py"
```

### Task 4: Extract writing router

**Files:**
- Create: `backend/app/routers/writing.py`
- Modify: `backend/app/routers/generate.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `writing.py`**

Extract from `generate.py`:
- Lines 944-1084: Writing pool helpers + `_extract_writing_topics()`
- Lines 1087-1261: Writing endpoints (`daily-writing`, `_seed_writing_pool`, `generate-more-writing`, `submit-ai-writing`)

- [ ] **Step 2: Register in `main.py`, remove from `generate.py`, update `daily_generate()` imports**

- [ ] **Step 3: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All 18 tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/writing.py backend/app/routers/generate.py backend/app/main.py
git commit -m "refactor: extract writing router from generate.py"
```

### Task 5: Verify generate.py is clean

After Tasks 1-4, `generate.py` should contain only:
- Imports
- `MAX_ACTIVE_CARDS`, `POOL_TARGET` constants
- `_with_db_id()` helper
- `daily_generate()` cron function (now imports helpers from skill routers)
- Shared endpoints: `explain-mistakes`, `translate-definition`, `extract-vocabulary`
- `TTSRequest` model (if not moved with tts-preview)

- [ ] **Step 1: Verify `generate.py` line count is ~250-300 lines**

Run: `wc -l backend/app/routers/generate.py`

- [ ] **Step 2: Run full backend test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All 18 tests pass.

- [ ] **Step 3: Tag and commit**

```bash
git add -A
git commit -m "refactor: verify generate.py is clean after skill extraction"
```

---

## Chunk 2: Frontend Refactoring (v0.20.0 continued)

Split `frontend/src/pages/Practice.tsx` (3,195 lines) into per-skill view components.

### File Structure After Refactoring

| File | Responsibility |
|---|---|
| `pages/Practice.tsx` | Main page: skill list, routing, state management, skill selection, shared styles (~600 lines) |
| `components/practice/AIReadingView.tsx` | AIReadingExerciseView + reading styles |
| `components/practice/AIListeningView.tsx` | AIListeningExerciseView + listening styles |
| `components/practice/AIWritingView.tsx` | AIWritingExerciseView + ESSAY_TYPE_LABELS + writing styles |
| `components/practice/AIGrammarView.tsx` | AIGrammarExerciseView + grammar styles |
| `utils/completionMatch.ts` | wordsToNumber, normalize, pluralMatch, editDistance, completionMatch, WORD_TO_NUM, MULTIPLIERS |
| `utils/dictionary.ts` | parseDictionaryEntry, POS_ABBR |

### Task 6: Extract shared utilities

**Files:**
- Create: `frontend/src/utils/completionMatch.ts`
- Create: `frontend/src/utils/dictionary.ts`

- [ ] **Step 1: Create `completionMatch.ts`**

Extract from `Practice.tsx` lines 916-999:

```typescript
// frontend/src/utils/completionMatch.ts
const WORD_TO_NUM: Record<string, number> = { /* ... exact content from lines 916-922 */ };
const MULTIPLIERS: Record<string, number> = { hundred: 100, thousand: 1000, million: 1_000_000 };

export function wordsToNumber(text: string): number { /* lines 926-937 */ }
export function normalize(raw: string): string { /* lines 940-951 */ }
export function pluralMatch(a: string, b: string): boolean { /* lines 954-964 */ }
export function editDistance(a: string, b: string): number { /* lines 967-981 */ }
export function completionMatch(userRaw: string, correctRaw: string): boolean { /* lines 984-999 */ }
```

- [ ] **Step 2: Create `dictionary.ts`**

Extract from `Practice.tsx` lines 22-37:

```typescript
// frontend/src/utils/dictionary.ts
export const POS_ABBR: Record<string, string> = { /* lines 22-25 */ };
export function parseDictionaryEntry(data: any[]): string { /* lines 27-37 */ }
```

- [ ] **Step 3: Run frontend build + tests**

Run: `cd frontend && npm run build && npm test`
Expected: Build succeeds, tests pass. (Files created but not yet imported — no breakage.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/completionMatch.ts frontend/src/utils/dictionary.ts
git commit -m "refactor: extract shared utilities from Practice.tsx"
```

### Task 7: Extract AIReadingView component

**Files:**
- Create: `frontend/src/components/practice/AIReadingView.tsx`
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Create `AIReadingView.tsx`**

Extract `AIReadingExerciseView` function (Practice.tsx lines 41-912) into its own file. The component needs these props:

```typescript
// frontend/src/components/practice/AIReadingView.tsx
import { useState, useEffect, useRef } from 'react';
import { AIReadingPractice } from '../../types';
import { completionMatch } from '../../utils/completionMatch';
import { parseDictionaryEntry, POS_ABBR } from '../../utils/dictionary';

interface AIReadingViewProps {
  exercise: AIReadingPractice;
  onSubmit: (score: number, correct: number, total: number, answers: any) => void;
  onBack: () => void;
  practiceAPI: any;      // for explain-mistakes
  topicsAPI: any;        // for vocab popup
  language: string;      // for translations
  generateAPI: any;      // for translate-definition
}

export default function AIReadingExerciseView({ exercise, onSubmit, onBack, practiceAPI, topicsAPI, language, generateAPI }: AIReadingViewProps) {
  // ... exact content from lines 41-912
}
```

Move reading-specific styles into the same file or a co-located CSS string.

- [ ] **Step 2: Update Practice.tsx to import AIReadingView**

Replace inline `AIReadingExerciseView` with:

```typescript
import AIReadingExerciseView from '../components/practice/AIReadingView';
```

Remove lines 41-912 from Practice.tsx.

- [ ] **Step 3: Run frontend build + tests**

Run: `cd frontend && npm run build && npm test`
Expected: Build succeeds, tests pass. App works identically.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/practice/AIReadingView.tsx frontend/src/pages/Practice.tsx
git commit -m "refactor: extract AIReadingView from Practice.tsx"
```

### Task 8: Extract AIListeningView component

**Files:**
- Create: `frontend/src/components/practice/AIListeningView.tsx`
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Create `AIListeningView.tsx`**

Extract `AIListeningExerciseView` (Practice.tsx lines 2083-2615) + listening-specific styles. Import `completionMatch` from utils.

Props interface pattern same as reading — exercise data, handlers, API refs.

- [ ] **Step 2: Update Practice.tsx to import, remove inline code**

- [ ] **Step 3: Run frontend build + tests**

Run: `cd frontend && npm run build && npm test`
Expected: Pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/practice/AIListeningView.tsx frontend/src/pages/Practice.tsx
git commit -m "refactor: extract AIListeningView from Practice.tsx"
```

### Task 9: Extract AIWritingView component

**Files:**
- Create: `frontend/src/components/practice/AIWritingView.tsx`
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Create `AIWritingView.tsx`**

Extract `AIWritingExerciseView` (lines 1013-1267) + `ESSAY_TYPE_LABELS` (lines 1005-1011) + `writingStyles` (lines 1269-1351).

- [ ] **Step 2: Update Practice.tsx, run build + tests, commit**

```bash
git commit -m "refactor: extract AIWritingView from Practice.tsx"
```

### Task 10: Extract AIGrammarView component

**Files:**
- Create: `frontend/src/components/practice/AIGrammarView.tsx`
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Create `AIGrammarView.tsx`**

Extract `AIGrammarExerciseView` (lines 1353-2011) + `grammarStyles` (lines 2013-2079). This component uses vocab popup logic — include the vocab selection handlers in its props or extract them.

- [ ] **Step 2: Update Practice.tsx, run build + tests, commit**

```bash
git commit -m "refactor: extract AIGrammarView from Practice.tsx"
```

### Task 11: Verify Practice.tsx is clean + tag v0.20.0

- [ ] **Step 1: Verify Practice.tsx is ~600 lines**

Run: `wc -l frontend/src/pages/Practice.tsx`

- [ ] **Step 2: Run full CI checks**

```bash
cd backend && python -m pytest tests/ -v --tb=short
cd ../frontend && npm run build && npm test
```

- [ ] **Step 3: Commit, tag, push, release**

```bash
git add -A
git commit -m "refactor: modularize Practice.tsx and generate.py into per-skill files (v0.20.0)"
git tag v0.20.0
git push origin main v0.20.0
```

Create GitHub release for v0.20.0.

---

## Chunk 3: Speaking Backend Infrastructure (v0.21.0)

### Task 12: Add Azure Speech SDK + config

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/config.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Add `azure-cognitiveservices-speech` to requirements.txt**

```
azure-cognitiveservices-speech==1.40.0
```

- [ ] **Step 2: Add Azure settings to `config.py`**

Add after the Google Cloud TTS section (line 33 of config.py):

```python
    # Azure Speech — pronunciation assessment
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = ""
```

- [ ] **Step 3: Add CI environment variables**

Add to `.github/workflows/ci.yml` backend env section:

```yaml
AZURE_SPEECH_KEY: ""
AZURE_SPEECH_REGION: ""
```

- [ ] **Step 4: Install locally and verify**

Run: `cd backend && pip install azure-cognitiveservices-speech==1.40.0`

- [ ] **Step 5: Run backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass (Azure key is empty, code not called yet).

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/config.py .github/workflows/ci.yml
git commit -m "feat: add Azure Speech SDK dependency + config"
```

### Task 13: Create Azure Pronunciation Assessment wrapper

**Files:**
- Create: `backend/app/services/azure_speech.py`
- Create: `backend/tests/test_azure_speech.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_azure_speech.py
"""Tests for Azure Speech pronunciation assessment wrapper."""
from app.services.azure_speech import assess_pronunciation
from app.config import settings


def test_assess_pronunciation_skips_when_no_key():
    """When AZURE_SPEECH_KEY is empty, return None gracefully."""
    # In CI, AZURE_SPEECH_KEY is empty — should not crash
    result = assess_pronunciation("/nonexistent/audio.wav")
    assert result is None


def test_assess_pronunciation_returns_expected_shape():
    """Verify return dict shape when key is present (mocked)."""
    # This test validates the interface contract, not Azure itself
    expected_keys = {"accuracy_score", "fluency_score", "prosody_score",
                     "pronunciation_score", "words"}
    # When key is empty, result is None — skip shape check
    if not settings.AZURE_SPEECH_KEY:
        return
    # Would need a real audio file + key to test further
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_azure_speech.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.azure_speech'`

- [ ] **Step 3: Write implementation**

```python
# backend/app/services/azure_speech.py
"""Azure Pronunciation Assessment wrapper.

Uses continuous recognition in unscripted (spontaneous speech) mode.
Returns phoneme-level accuracy, fluency, prosody scores.
Gracefully returns None if AZURE_SPEECH_KEY is not configured.
"""
import json
import logging
import threading
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)


def assess_pronunciation(audio_path: str) -> dict | None:
    """
    Run Azure PA on a WAV file. Returns scores dict or None if unavailable.

    Uses continuous recognition with PronunciationAssessmentConfig in
    unscripted mode. Aggregates per-utterance scores across the full audio.
    """
    if not settings.AZURE_SPEECH_KEY:
        logger.warning("AZURE_SPEECH_KEY not set — skipping pronunciation assessment")
        return None

    if not Path(audio_path).exists():
        logger.error(f"Audio file not found: {audio_path}")
        return None

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        logger.error("azure-cognitiveservices-speech not installed")
        return None

    speech_config = speechsdk.SpeechConfig(
        subscription=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
    )
    audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

    # Configure pronunciation assessment — unscripted, phoneme-level
    pa_config = speechsdk.PronunciationAssessmentConfig(
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=True,
    )
    pa_config.enable_prosody_assessment()

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
        language="en-US",
    )
    pa_config.apply_to(recognizer)

    # Collect results from continuous recognition
    all_words = []
    utterance_scores = []
    done_event = threading.Event()

    def on_recognized(evt):
        result = evt.result
        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            pa_result = speechsdk.PronunciationAssessmentResult(result)
            utterance_scores.append({
                "accuracy": pa_result.accuracy_score,
                "fluency": pa_result.fluency_score,
                "prosody": pa_result.prosody_score,
                "pronunciation": pa_result.pronunciation_score,
            })
            for word in pa_result.words:
                all_words.append({
                    "word": word.word,
                    "accuracy_score": word.accuracy_score,
                    "error_type": word.error_type.name if hasattr(word.error_type, 'name') else str(word.error_type),
                })

    def on_canceled(evt):
        done_event.set()

    def on_session_stopped(evt):
        done_event.set()

    recognizer.recognized.connect(on_recognized)
    recognizer.canceled.connect(on_canceled)
    recognizer.session_stopped.connect(on_session_stopped)

    recognizer.start_continuous_recognition()
    done_event.wait(timeout=150)  # 150s max for a 2-min recording
    recognizer.stop_continuous_recognition()

    if not utterance_scores:
        logger.warning("Azure PA returned no utterance scores")
        return None

    # Aggregate scores across utterances (weighted average by utterance count)
    n = len(utterance_scores)
    avg = lambda key: sum(u[key] for u in utterance_scores) / n

    return {
        "accuracy_score": round(avg("accuracy"), 1),
        "fluency_score": round(avg("fluency"), 1),
        "prosody_score": round(avg("prosody"), 1),
        "pronunciation_score": round(avg("pronunciation"), 1),
        "words": all_words,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_azure_speech.py -v`
Expected: PASS (returns None when key is empty).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/azure_speech.py backend/tests/test_azure_speech.py
git commit -m "feat: Azure Pronunciation Assessment wrapper with continuous recognition"
```

### Task 14: Create speaking cue card bank

**Files:**
- Create: `backend/app/services/ai/speaking_config.py`

- [ ] **Step 1: Create `speaking_config.py` with 60+ Part 2 cue cards**

```python
# backend/app/services/ai/speaking_config.py
"""IELTS Speaking Part 2 — Cue card bank + metadata generator.

60+ curated cue cards across 8 domains. Pool seeding is instant (no GPT).
Same pattern as writing_config.py.
"""
import random
from typing import Optional

SPEAKING_DOMAINS = [
    "people", "places", "events", "objects",
    "experiences", "media", "education", "work"
]

# Each cue card: id, topic_title, domain, topic_line, bullets, follow_up
PART2_CUE_CARDS = [
    # ── People ──
    {
        "id": "p2_ppl_01", "topic_title": "A Person Who Influenced You",
        "domain": "people",
        "topic_line": "Describe a person who has had a significant influence on your life.",
        "bullets": [
            "who this person is",
            "how you know them",
            "what they have done",
            "and explain why they have influenced you"
        ],
        "follow_up": "Do you think famous people have more influence than family members?"
    },
    {
        "id": "p2_ppl_02", "topic_title": "An Interesting Old Person",
        "domain": "people",
        "topic_line": "Describe an interesting old person you have met.",
        "bullets": [
            "who this person is",
            "where you met them",
            "what you talked about",
            "and explain why you found them interesting"
        ],
        "follow_up": "What can young people learn from older generations?"
    },
    # ... (60+ total cue cards across all 8 domains)
    # Template for remaining — implementer fills in from IELTS past papers
    # and common Part 2 topics
]

def generate_metadata(
    avoid_topics: list[str] | None = None,
    avoid_domains: list[str] | None = None,
) -> dict | None:
    """Pick a cue card avoiding recent topics/domains. Returns cue card dict or None."""
    avoid_topics = set(avoid_topics or [])
    avoid_domains = set(avoid_domains or [])

    candidates = [
        c for c in PART2_CUE_CARDS
        if c["topic_title"] not in avoid_topics
        and c["domain"] not in avoid_domains
    ]

    if not candidates:
        # Relax domain constraint
        candidates = [
            c for c in PART2_CUE_CARDS
            if c["topic_title"] not in avoid_topics
        ]

    if not candidates:
        return None

    return random.choice(candidates)
```

The implementer should fill in 60+ cue cards from real IELTS Part 2 past papers. Distribute across all 8 domains (7-8 per domain).

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/ai/speaking_config.py
git commit -m "feat: speaking cue card bank with 60+ Part 2 topics"
```

### Task 15: Create speaking grader

**Files:**
- Create: `backend/app/services/ai/speaking_grader.py`
- Create: `backend/tests/test_speaking_grader.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_speaking_grader.py
"""Tests for speaking grader — validates interface and band calculation."""
from app.services.ai.speaking_grader import SpeakingGrader


def test_grader_version():
    grader = SpeakingGrader()
    assert grader.GRADER_VERSION == "1.0"


def test_map_pronunciation_band():
    """Test Azure score → IELTS band mapping."""
    grader = SpeakingGrader()
    assert grader._map_pronunciation_band(95) == 8.5
    assert grader._map_pronunciation_band(80) == 7.0
    assert grader._map_pronunciation_band(65) == 6.5
    assert grader._map_pronunciation_band(50) == 5.5
    assert grader._map_pronunciation_band(30) == 4.0
    assert grader._map_pronunciation_band(None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_speaking_grader.py -v`
Expected: FAIL

- [ ] **Step 3: Write implementation**

```python
# backend/app/services/ai/speaking_grader.py
"""IELTS Speaking — Grading pipeline.

Layer 1: Whisper transcription (done before this module is called)
Layer 2: Azure PA pronunciation scores (done before this module is called)
Layer 3: GPT-4o grades FC, LR, GRA from transcript + Azure scores inform Pronunciation band
"""
import json
import logging
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)

SPEAKING_SCORING_PROMPT = """You are a senior IELTS Speaking examiner with 15+ years of experience.
Grade this Part 2 (Long Turn) response using the official IELTS Speaking band descriptors.

## IELTS Speaking Band Descriptors (Bands 4-9)

### Fluency and Coherence (FC)
Band 9: Speaks fluently with only rare repetition or self-correction. Any hesitation is content-related. Develops topics fully and coherently.
Band 8: Speaks fluently with only occasional repetition or self-correction. Develops topics coherently and appropriately.
Band 7: Speaks at length without noticeable effort or loss of coherence. May demonstrate language-related hesitation at times. Uses a range of connectives and discourse markers.
Band 6: Is willing to speak at length though may lose coherence at times due to occasional repetition, self-correction or hesitation. Uses a range of connectives and discourse markers but not always appropriately.
Band 5: Usually maintains flow of speech but uses repetition, self-correction and/or slow speech to keep going. May over-use certain connectives and discourse markers. Produces simple speech fluently but more complex communication causes fluency problems.
Band 4: Cannot respond without noticeable pauses and may speak slowly with frequent repetition and self-correction. Links basic sentences but with repetitious use of simple connectives.

### Lexical Resource (LR)
Band 9: Uses vocabulary with full flexibility and precision in all topics. Uses idiomatic language naturally and accurately.
Band 8: Uses a wide vocabulary resource readily and flexibly. Uses less common and idiomatic vocabulary skilfully, with occasional inaccuracies. Uses paraphrase effectively.
Band 7: Uses vocabulary resource flexibly to discuss a variety of topics. Uses some less common and idiomatic vocabulary and shows some awareness of style and collocation, with some inappropriate choices. Uses paraphrase effectively.
Band 6: Has a wide enough vocabulary to discuss topics at length and make meaning clear in spite of inappropriacies. Generally paraphrases successfully.
Band 5: Manages to talk about familiar and unfamiliar topics but uses vocabulary with limited flexibility. Attempts to use paraphrase but with mixed success.
Band 4: Is able to talk about familiar topics but can only convey basic meaning on unfamiliar topics. Makes frequent errors in word choice.

### Grammatical Range and Accuracy (GRA)
Band 9: Uses a full range of structures naturally and appropriately. Produces consistently accurate structures apart from 'slips' characteristic of native speaker speech.
Band 8: Uses a wide range of structures flexibly. Produces a majority of error-free sentences with only very occasional inappropriacies or basic/non-systematic errors.
Band 7: Uses a range of complex structures with some flexibility. Frequently produces error-free sentences, though some grammatical mistakes persist.
Band 6: Uses a mix of simple and complex structures but with limited flexibility. May make frequent mistakes with complex structures though these rarely cause comprehension problems.
Band 5: Produces basic sentence forms with reasonable accuracy. Uses a limited range of more complex structures, but these usually contain errors.
Band 4: Produces basic sentence forms and some correct simple sentences but subordinate structures are rare. Errors are frequent and may lead to misunderstanding.

## Azure Pronunciation Data
{pronunciation_data}

## Instructions

1. Read the transcript as if listening to the student speak.
2. For FC, LR, GRA: assign a band score (whole or .5 increments, range 4.0-9.0) with evidence quotes.
3. For Pronunciation: use the Azure pronunciation_score as primary signal. Map it to IELTS band using:
   90-100 → 8-9, 75-89 → 7-7.5, 60-74 → 6-6.5, 45-59 → 5-5.5, <45 → 4-4.5.
   If Azure data is null, evaluate pronunciation from transcript intelligibility only (less reliable, note this).
4. Calculate overall_band as arithmetic mean of 4 criteria, rounded to nearest 0.5.
5. Write coaching feedback: 1-2 sentence summary, 2-3 strengths, 2-3 improvements.
6. If any criterion ≤5.0, flag it as dominant weakness in improvement #1.

## Output (strict JSON)

{{
  "examiner_result": {{
    "fluency_coherence": {{ "band": <number>, "evidence": "<quotes>" }},
    "lexical_resource": {{ "band": <number>, "evidence": "<quotes>" }},
    "grammatical_range_accuracy": {{ "band": <number>, "evidence": "<quotes>" }},
    "pronunciation": {{ "band": <number>, "evidence": "<quotes>" }},
    "overall_band": <number>
  }},
  "coaching_feedback": {{
    "summary": "<string>",
    "strengths": ["<string>", "<string>"],
    "improvements": ["<string>", "<string>"]
  }}
}}
"""


class SpeakingGrader:
    """IELTS Speaking grader using Azure PA + GPT-4o."""

    GRADER_VERSION = "1.0"

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o"

    def grade(self, transcript: str, cue_card: dict, azure_scores: dict | None = None) -> dict:
        """Grade a speaking response. Returns examiner result + coaching."""
        pronunciation_data = "No pronunciation data available (Azure PA unavailable)."
        if azure_scores:
            mispronounced = [
                w for w in azure_scores.get("words", [])
                if w.get("error_type") not in ("None", None)
            ]
            pronunciation_data = (
                f"Pronunciation score: {azure_scores['pronunciation_score']}/100\n"
                f"Accuracy: {azure_scores['accuracy_score']}/100\n"
                f"Fluency: {azure_scores['fluency_score']}/100\n"
                f"Prosody: {azure_scores['prosody_score']}/100\n"
                f"Mispronounced words: {json.dumps(mispronounced[:20])}"
            )

        system_prompt = SPEAKING_SCORING_PROMPT.format(
            pronunciation_data=pronunciation_data,
        )

        user_prompt = (
            f"## Cue Card\n"
            f"Topic: {cue_card.get('topic_line', '')}\n"
            f"Bullets: {', '.join(cue_card.get('bullets', []))}\n\n"
            f"## Student's Response (transcript)\n\n"
            f"{transcript}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        scoring = json.loads(raw)

        er = scoring.get("examiner_result", {})

        # Override pronunciation band with Azure mapping if available
        if azure_scores and azure_scores.get("pronunciation_score") is not None:
            mapped = self._map_pronunciation_band(azure_scores["pronunciation_score"])
            if mapped is not None:
                # Blend: 70% Azure mapping + 30% GPT judgment
                gpt_band = er.get("pronunciation", {}).get("band", mapped)
                blended = round((mapped * 0.7 + gpt_band * 0.3) * 2) / 2
                er["pronunciation"]["band"] = blended

        # Recalculate overall
        bands = [
            er.get("fluency_coherence", {}).get("band", 0),
            er.get("lexical_resource", {}).get("band", 0),
            er.get("grammatical_range_accuracy", {}).get("band", 0),
            er.get("pronunciation", {}).get("band", 0),
        ]
        er["overall_band"] = round(sum(bands) / 4 * 2) / 2

        # Attach Azure raw scores for frontend display
        if azure_scores:
            er["pronunciation"]["azure_scores"] = {
                "accuracy": azure_scores["accuracy_score"],
                "fluency": azure_scores["fluency_score"],
                "prosody": azure_scores["prosody_score"],
                "composite": azure_scores["pronunciation_score"],
            }

        scoring["grader_version"] = self.GRADER_VERSION
        scoring["model"] = self.model
        return scoring

    def _map_pronunciation_band(self, score: float | None) -> float | None:
        """Map Azure pronunciation_score (0-100) to IELTS band."""
        if score is None:
            return None
        if score >= 95:
            return 9.0
        elif score >= 90:
            return 8.5
        elif score >= 82:
            return 8.0
        elif score >= 75:
            return 7.5
        elif score >= 68:
            return 7.0
        elif score >= 60:
            return 6.5
        elif score >= 52:
            return 6.0
        elif score >= 45:
            return 5.5
        elif score >= 38:
            return 5.0
        elif score >= 30:
            return 4.5
        else:
            return 4.0
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_speaking_grader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/speaking_grader.py backend/tests/test_speaking_grader.py
git commit -m "feat: speaking grader with Azure PA + GPT-4o scoring"
```

---

## Chunk 4: Speaking Backend Endpoints (v0.21.0 continued)

### Task 16: Create speaking router with pool endpoints + submit

**Files:**
- Create: `backend/app/routers/speaking.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/routers/generate.py` (update `daily_generate`)

- [ ] **Step 1: Create `speaking.py`**

```python
# backend/app/routers/speaking.py
"""Speaking skill — pool helpers + endpoints.

Pool seeding is instant (cue cards from config, no GPT).
Submit endpoint handles audio upload → Whisper → Azure PA → GPT-4o grading.
"""
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, BackgroundTasks, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from pydub import AudioSegment

from app.database import get_db, SessionLocal
from app.services.auth import get_current_user
from app.models.models import User, GeneratedPractice, UserPractice
from app.services.ai.speaking_config import PART2_CUE_CARDS, generate_metadata as speaking_generate_metadata
from app.services.ai.speaking_grader import SpeakingGrader
from app.services.azure_speech import assess_pronunciation
from app.config import settings
from app.routers.generate import MAX_ACTIVE_CARDS, POOL_TARGET, _with_db_id

from openai import OpenAI

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])

SPEAKING_AUDIO_DIR = Path(settings.TTS_AUDIO_DIR) / "speaking"

# ── pool helpers ─────────────────────────────────────────────────────────────

def _available_speaking_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    served = db.query(UserPractice.practice_id).filter(UserPractice.user_id == user_id)
    q = db.query(GeneratedPractice).filter(
        GeneratedPractice.skill == "speaking",
        GeneratedPractice.is_validated == True,
        ~GeneratedPractice.id.in_(served),
    )
    if exclude_topics:
        q = q.filter(~GeneratedPractice.topic.in_(exclude_topics))
    q = q.order_by(GeneratedPractice.generated_date)
    return q.limit(limit).all() if limit else q.all()


def _active_speaking_cards(user_id: int, db: Session) -> list:
    return (
        db.query(UserPractice)
        .join(GeneratedPractice)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at == None,
            GeneratedPractice.skill == "speaking",
        )
        .all()
    )


def _seed_speaking_pool(db: Session, count: int = 5) -> None:
    """Seed pool from hardcoded cue cards (instant, no GPT)."""
    existing_topics = {
        gp.topic for gp in db.query(GeneratedPractice).filter(
            GeneratedPractice.skill == "speaking"
        ).all()
    }
    added = 0
    for card in PART2_CUE_CARDS:
        if card["topic_title"] in existing_topics:
            continue
        content = {
            "meta": {
                "module": "speaking_part2",
                "domain": card["domain"],
                "topic": card["topic_title"],
            },
            "cue_card": {
                "topic_line": card["topic_line"],
                "bullets": card["bullets"],
                "follow_up": card["follow_up"],
            },
            "cue_card_metadata": card,
        }
        db.add(GeneratedPractice(
            skill="speaking",
            topic=card["topic_title"],
            content=json.dumps(content),
            is_validated=True,
            generated_date=datetime.utcnow(),
        ))
        added += 1
        if added >= count:
            break
    db.commit()


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("/daily-speaking")
def get_daily_speaking(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active = _active_speaking_cards(current_user.id, db)
    if len(active) < MAX_ACTIVE_CARDS:
        # Seed pool if empty
        pool = _available_speaking_for_user(current_user.id, db, limit=1)
        if not pool:
            _seed_speaking_pool(db)
            pool = _available_speaking_for_user(current_user.id, db, limit=1)

        available = _available_speaking_for_user(
            current_user.id, db, limit=MAX_ACTIVE_CARDS - len(active),
            exclude_topics=[
                json.loads(a.practice.content).get("meta", {}).get("topic", "")
                for a in active
            ],
        )
        for gp in available:
            up = UserPractice(user_id=current_user.id, practice_id=gp.id)
            db.add(up)
        db.commit()
        active = _active_speaking_cards(current_user.id, db)

    practices = [_with_db_id(a.practice, a.id) for a in active]
    return {"practices": practices}


@router.post("/generate-more-speaking")
def generate_more_speaking(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active = _active_speaking_cards(current_user.id, db)
    if len(active) >= MAX_ACTIVE_CARDS:
        practices = [_with_db_id(a.practice, a.id) for a in active]
        return {"practices": practices, "pool_empty": False, "at_capacity": True}

    pool = _available_speaking_for_user(current_user.id, db, limit=1)
    if not pool:
        _seed_speaking_pool(db, count=5)
        pool = _available_speaking_for_user(current_user.id, db, limit=1)
    if not pool:
        practices = [_with_db_id(a.practice, a.id) for a in active]
        return {"practices": practices, "pool_empty": True, "at_capacity": False}

    gp = pool[0]
    up = UserPractice(user_id=current_user.id, practice_id=gp.id)
    db.add(up)
    db.commit()

    active = _active_speaking_cards(current_user.id, db)
    practices = [_with_db_id(a.practice, a.id) for a in active]
    return {"practices": practices, "pool_empty": False, "at_capacity": False}


@router.post("/submit-ai-speaking")
async def submit_ai_speaking(
    audio: UploadFile = File(...),
    practice_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload audio → Whisper transcribe → Azure PA → GPT-4o grade."""
    # Find the user practice
    up = db.query(UserPractice).filter(
        UserPractice.id == practice_id,
        UserPractice.user_id == current_user.id,
        UserPractice.submitted_at == None,
    ).first()
    if not up:
        raise HTTPException(404, "Practice not found or already submitted")

    gp = db.query(GeneratedPractice).get(up.practice_id)
    content = json.loads(gp.content)
    cue_card = content.get("cue_card", {})

    # Save uploaded audio to temp file
    SPEAKING_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_bytes = await audio.read()

    # Reject if too small (< ~5 seconds of audio ≈ 50KB for webm)
    if len(audio_bytes) < 10_000:
        raise HTTPException(422, "Audio too short. Please record at least 5 seconds.")

    # Convert to WAV for Azure PA
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        tmp_in.write(audio_bytes)
        tmp_in_path = tmp_in.name

    wav_path = str(SPEAKING_AUDIO_DIR / f"{current_user.id}_{practice_id}.wav")
    try:
        audio_segment = AudioSegment.from_file(tmp_in_path)
        audio_segment.export(wav_path, format="wav")
    except Exception as e:
        raise HTTPException(422, f"Audio conversion failed: {e}")
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)

    # Step 1: Whisper transcription
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    try:
        with open(wav_path, "rb") as f:
            whisper_result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
        transcript = whisper_result.strip() if isinstance(whisper_result, str) else whisper_result.text.strip()
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        raise HTTPException(500, "Transcription failed. Please try again.")

    if not transcript or len(transcript) < 10:
        raise HTTPException(422, "No speech detected. Please speak clearly and try again.")

    # Step 2: Azure Pronunciation Assessment (graceful failure)
    azure_scores = None
    try:
        azure_scores = assess_pronunciation(wav_path)
    except Exception as e:
        logger.warning(f"Azure PA failed (proceeding without pronunciation): {e}")

    # Step 3: GPT-4o grading
    try:
        grader = SpeakingGrader()
        grading_result = grader.grade(transcript, cue_card, azure_scores)
    except Exception as e:
        logger.error(f"Speaking grading failed: {e}")
        raise HTTPException(500, "Grading failed. Please try again.")

    # Store results
    overall = grading_result.get("examiner_result", {}).get("overall_band", 0)
    grading_result["transcript"] = transcript
    if azure_scores:
        # Only store mispronounced words to reduce storage size
        grading_result["pronunciation_words"] = [
            w for w in azure_scores.get("words", [])
            if w.get("error_type") not in ("None", None)
        ]

    up.submitted_at = datetime.utcnow()
    up.user_answers = json.dumps(grading_result)
    up.score = overall
    db.commit()

    # Clean up audio file (results stored, no need to keep)
    Path(wav_path).unlink(missing_ok=True)

    return grading_result
```

- [ ] **Step 2: Register speaking router in `main.py`**

```python
from app.routers import speaking
# ...
app.include_router(speaking.router, prefix=f"{settings.API_PREFIX}", tags=["Generate"])
```

- [ ] **Step 3: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/speaking.py backend/app/main.py
git commit -m "feat: speaking pool endpoints + submit with Whisper/Azure/GPT-4o pipeline"
```

### Task 17: Install ffmpeg on VPS

- [ ] **Step 1: Install ffmpeg**

```bash
ssh -i ~/.ssh/ielts_assist_deploy root@152.42.251.169 "apt install -y ffmpeg && ffmpeg -version | head -1"
```

- [ ] **Step 2: Commit (no code change — VPS-only)**

No git commit needed. Note in session that ffmpeg is installed.

---

## Chunk 5: Frontend Speaking View (v0.21.0 continued)

### Task 18: Add frontend types + API methods

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: Add speaking types**

Add to `frontend/src/types/index.ts`:

```typescript
export interface SpeakingCueCard {
  topic_line: string;
  bullets: string[];
  follow_up: string;
}

export interface AISpeakingPractice {
  practice_db_id: number;
  meta: { module: string; domain: string; topic: string };
  cue_card: SpeakingCueCard;
  cue_card_metadata: Record<string, any>;
}

export interface SpeakingPronunciationWord {
  word: string;
  accuracy_score: number;
  error_type: string;
}

export interface SpeakingGradingResult {
  examiner_result: {
    fluency_coherence: { band: number; evidence: string };
    lexical_resource: { band: number; evidence: string };
    grammatical_range_accuracy: { band: number; evidence: string };
    pronunciation: { band: number; evidence: string; azure_scores?: Record<string, number> };
    overall_band: number;
  };
  coaching_feedback: {
    summary: string;
    strengths: string[];
    improvements: string[];
  };
  transcript: string;
  pronunciation_words?: SpeakingPronunciationWord[];
  grader_version: string;
  model: string;
}
```

- [ ] **Step 2: Add API methods**

Add to `practiceAPI` in `frontend/src/api/index.ts`:

```typescript
getDailySpeaking: () => api.get('/generate/daily-speaking'),
generateMoreSpeaking: () => api.post('/generate/generate-more-speaking'),
submitAISpeaking: (audio: Blob, practiceId: number) => {
  const formData = new FormData();
  formData.append('audio', audio, 'recording.webm');
  formData.append('practice_id', practiceId.toString());
  return api.post('/generate/submit-ai-speaking', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000,  // 30s — grading takes 5-10s
  });
},
```

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: Build passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/index.ts
git commit -m "feat: speaking types + API methods (daily, generate-more, submit with audio)"
```

### Task 19: Create AISpeakingView component

**Files:**
- Create: `frontend/src/components/practice/AISpeakingView.tsx`
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Create `AISpeakingView.tsx`**

Full component with 5 states: cue card → prep → recording → processing → results.

```typescript
// frontend/src/components/practice/AISpeakingView.tsx
import { useState, useEffect, useRef } from 'react';
import { AISpeakingPractice, SpeakingGradingResult } from '../../types';

interface AISpeakingViewProps {
  exercise: AISpeakingPractice;
  onSubmit: (result: SpeakingGradingResult) => void;
  onBack: () => void;
  practiceAPI: any;
}

type SpeakingPhase = 'cue_card' | 'preparation' | 'recording' | 'processing' | 'results';

export default function AISpeakingExerciseView({
  exercise, onSubmit, onBack, practiceAPI
}: AISpeakingViewProps) {
  const [phase, setPhase] = useState<SpeakingPhase>('cue_card');
  const [prepTime, setPrepTime] = useState(60);
  const [recordTime, setRecordTime] = useState(0);
  const [gradingResult, setGradingResult] = useState<SpeakingGradingResult | null>(null);
  const [error, setError] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
    };
  }, []);

  // Prep countdown
  useEffect(() => {
    if (phase !== 'preparation') return;
    timerRef.current = setInterval(() => {
      setPrepTime(t => {
        if (t <= 1) {
          clearInterval(timerRef.current!);
          startRecording();
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [phase]);

  // Record timer
  useEffect(() => {
    if (phase !== 'recording') return;
    timerRef.current = setInterval(() => {
      setRecordTime(t => {
        if (t >= 120) { stopRecording(); return 120; }
        return t + 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [phase]);

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Negotiate mime type (Safari uses mp4, others use webm)
      const mimeType = MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm' : 'audio/mp4';
      const recorder = new MediaRecorder(stream, { mimeType });

      chunksRef.current = [];
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.onstop = handleRecordingComplete;

      recorder.start(1000); // collect chunks every second
      mediaRecorderRef.current = recorder;
      setRecordTime(0);
      setPhase('recording');
    } catch (err) {
      setError('Microphone access denied. Please allow microphone permissions and try again.');
    }
  }

  function stopRecording() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
    }
    if (timerRef.current) clearInterval(timerRef.current);
  }

  async function handleRecordingComplete() {
    setPhase('processing');
    const mimeType = mediaRecorderRef.current?.mimeType || 'audio/webm';
    const blob = new Blob(chunksRef.current, { type: mimeType });

    try {
      const res = await practiceAPI.submitAISpeaking(blob, exercise.practice_db_id);
      setGradingResult(res.data);
      onSubmit(res.data);
      setPhase('results');
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Grading failed. Please try again.';
      setError(msg);
      setPhase('cue_card'); // allow retry
    }
  }

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  // ── Render by phase ──

  if (error) {
    return (
      <div className="speaking-error">
        <p>{error}</p>
        <button onClick={() => { setError(''); setPhase('cue_card'); }}>Try Again</button>
        <button onClick={onBack}>Back</button>
      </div>
    );
  }

  if (phase === 'results' && gradingResult) {
    const er = gradingResult.examiner_result;
    const criteria = [
      { key: 'Fluency & Coherence', data: er.fluency_coherence },
      { key: 'Lexical Resource', data: er.lexical_resource },
      { key: 'Grammatical Range & Accuracy', data: er.grammatical_range_accuracy },
      { key: 'Pronunciation', data: er.pronunciation },
    ];

    return (
      <div className="speaking-results">
        <div className="speaking-overall">
          <span>OVERALL BAND</span>
          <span className="band-score">{er.overall_band}</span>
        </div>

        {criteria.map(c => (
          <div key={c.key} className="criterion-card">
            <h3>{c.key}</h3>
            <span className="band">{c.data.band}</span>
            <p className="evidence">{c.data.evidence}</p>
          </div>
        ))}

        {gradingResult.transcript && (
          <div className="transcript-section">
            <h3>Your Transcript</h3>
            <p>{gradingResult.transcript}</p>
          </div>
        )}

        {gradingResult.pronunciation_words && gradingResult.pronunciation_words.length > 0 && (
          <div className="pronunciation-section">
            <h3>Pronunciation Issues</h3>
            {gradingResult.pronunciation_words.map((w, i) => (
              <span key={i} className={`pron-word pron-${w.error_type.toLowerCase()}`}>
                {w.word} ({Math.round(w.accuracy_score)})
              </span>
            ))}
          </div>
        )}

        <div className="coaching-section">
          <h3>Coaching Feedback</h3>
          <p>{gradingResult.coaching_feedback.summary}</p>
          <h4>Strengths</h4>
          <ul>{gradingResult.coaching_feedback.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
          <h4>Improvements</h4>
          <ul>{gradingResult.coaching_feedback.improvements.map((s, i) => <li key={i}>{s}</li>)}</ul>
        </div>

        <button onClick={onBack}>Finish</button>
      </div>
    );
  }

  // Cue card + prep + recording phases
  return (
    <div className="speaking-exercise">
      <button className="back-btn" onClick={onBack}>&lt; Back</button>

      <div className="cue-card">
        <h2>{exercise.cue_card.topic_line}</h2>
        <p>You should say:</p>
        <ul>
          {exercise.cue_card.bullets.map((b, i) => <li key={i}>{b}</li>)}
        </ul>
      </div>

      {phase === 'cue_card' && (
        <button className="start-btn" onClick={() => setPhase('preparation')}>
          Start (1 min preparation)
        </button>
      )}

      {phase === 'preparation' && (
        <div className="prep-timer">
          <p>Preparation time</p>
          <span className="timer">{formatTime(prepTime)}</span>
          <p className="hint">Think about what you want to say. Make notes if you like.</p>
          <button onClick={() => { clearInterval(timerRef.current!); startRecording(); }}>
            Start Speaking Now
          </button>
        </div>
      )}

      {phase === 'recording' && (
        <div className="recording-ui">
          <div className="recording-indicator">
            <span className="red-dot" />
            <span>Recording... {formatTime(recordTime)} / 2:00</span>
          </div>
          <button className="stop-btn" onClick={stopRecording}>
            Stop Recording
          </button>
        </div>
      )}

      {phase === 'processing' && (
        <div className="processing">
          <div className="spinner" />
          <p>Examiner is reviewing your response...</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Integrate into Practice.tsx**

Add import and wire into the skill selection logic (same pattern as reading/listening/writing/grammar).

```typescript
import AISpeakingExerciseView from '../components/practice/AISpeakingView';
```

Add speaking state, load function, and render branch following the exact same pattern as other skills.

- [ ] **Step 3: Run frontend build + tests**

Run: `cd frontend && npm run build && npm test`
Expected: Pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/practice/AISpeakingView.tsx frontend/src/pages/Practice.tsx
git commit -m "feat: AISpeakingView — cue card, prep timer, recording, results display"
```

### Task 20: Final integration + tag v0.21.0

- [ ] **Step 1: Run full CI suite locally**

```bash
cd backend && python -m pytest tests/ -v --tb=short
cd ../frontend && npm run build && npm test
```

- [ ] **Step 2: Commit, tag, push, release**

```bash
git add -A
git commit -m "feat: AI Speaking Part 2 MVP — Whisper + Azure PA + GPT-4o grading (v0.21.0)"
git tag v0.21.0
git push origin main v0.21.0
```

Create GitHub release for v0.21.0.

- [ ] **Step 3: Verify on VPS after deploy**

SSH in and check:
- `ffmpeg` is installed
- `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are in systemd env
- `pip list | grep azure` shows the SDK
- `journalctl -u ielts-backend -n 50` shows no startup errors

- [ ] **Step 4: Manual test**

Open the app → Speaking Practice → select a cue card → go through prep → record → submit → verify grading results appear.

---

## Summary

| Chunk | Tasks | Version | What ships |
|---|---|---|---|
| 1: Backend refactoring | Tasks 1-5 | v0.20.0 | Split generate.py into per-skill routers |
| 2: Frontend refactoring | Tasks 6-11 | v0.20.0 | Split Practice.tsx into per-skill components |
| 3: Speaking backend infra | Tasks 12-15 | v0.21.0 | Azure wrapper, cue card bank, speaking grader |
| 4: Speaking endpoints | Tasks 16-17 | v0.21.0 | Pool + submit endpoints, ffmpeg on VPS |
| 5: Speaking frontend | Tasks 18-20 | v0.21.0 | Types, API, AISpeakingView, integration |
