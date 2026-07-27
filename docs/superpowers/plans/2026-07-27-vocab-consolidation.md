# Vocabulary Lookup Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the browser's direct calls to `dictionaryapi.dev` with one backend endpoint that returns definition, IPA, Chinese translation and self-hosted pronunciation audio — cached in Postgres and shared across users.

**Architecture:** A single `POST /api/generate/define-word` does one `utility`-tier model call (definition + IPA + Chinese + example) and one Google TTS call (pronunciation MP3 written to the existing audio directory). Results are cached in a new `vocab_cache` table keyed by the lowercased word, so the same word is generated once for the entire user base. The frontend's three duplicated fetch sites collapse to one API call.

**Tech Stack:** FastAPI, SQLAlchemy, Google Cloud TTS (already integrated), React.

---

## 1. Why

### It is a hard dependency on a free service with no contract

`api.dictionaryapi.dev` is called **directly from the browser** in three places:

| File | Line |
|---|---|
| `frontend/src/components/practice/AIGrammarView.tsx` | 80 |
| `frontend/src/hooks/useVocabSelection.ts` | 30 |
| `frontend/src/pages/Topics.tsx` | 83 |

No API key, no SLA, no rate-limit guarantee. If it throttles or disappears, vocabulary lookup breaks for every user at once.

### Worse: the damage is retroactive

`Topic.audio_url` stores the URL that service returns — its own comment says so:

```python
audio_url = Column(String(500), nullable=True)  # MP3 from dictionaryapi.dev
```

Those rows are permanent. If the service goes away, **every word a user has already saved loses its audio**, not just new lookups. Self-hosting the audio is what makes saved vocabulary durable.

### Two incidental wins

- **British pronunciation.** dictionaryapi.dev returns whatever accent its contributor recorded. Google TTS with an `en-GB` voice gives consistent British audio, which is what IELTS candidates should be training against.
- **Kills a duplicate.** `parseDictionaryEntry` exists twice — `frontend/src/utils/dictionary.ts:6` returns a string, while `frontend/src/pages/Topics.tsx:13` is a divergent copy returning `{content, example}`. `CLAUDE.md` says never duplicate code; both disappear with the API response.

### Cost is negligible and one-time per word

~$0.0005 for the model call plus ~$0.0002 for TTS on first lookup, then **$0 forever** — for every user, because the cache is global. IELTS vocabulary repeats heavily across students.

## 2. Decisions taken

1. **Audio is self-hosted.** Generated once via Google TTS into `settings.TTS_AUDIO_DIR`, which `deploy.yml` already preserves across deploys. No external audio dependency remains.
2. **Cache is global, not per-user.** Definitions are not user-specific, so `vocab_cache` has no `user_id`.
3. **Existing rows are left alone.** Old `audio_url` values keep pointing at dictionaryapi.dev until that word is looked up again. A backfill is out of scope — noted as a follow-up rather than bundled into this change.
4. **The endpoint lives in `generate.py`**, next to `translate-definition`, which it supersedes.

## 3. File structure

| File | Responsibility |
|---|---|
| `backend/app/models/models.py` | **Modify.** Add `VocabCache`; update the stale `audio_url` comment. |
| `backend/app/services/vocab.py` | **Create.** Lookup + cache + TTS orchestration. |
| `backend/app/routers/generate.py` | **Modify.** Add `POST /define-word`; retire `translate-definition`. |
| `backend/tests/test_vocab.py` | **Create.** Cache hit/miss, parsing, TTS failure tolerance. |
| `frontend/src/utils/dictionary.ts` | **Modify.** Replace parser with a typed API client. |
| `frontend/src/hooks/useVocabSelection.ts` | **Modify.** Call the backend. |
| `frontend/src/pages/Topics.tsx` | **Modify.** Call the backend; delete the duplicate parser. |
| `frontend/src/components/practice/AIGrammarView.tsx` | **Modify.** Call the backend. |

---

## Task 1: VocabCache model

**Files:** Modify `backend/app/models/models.py`

- [ ] **Step 1: Add the model** after `Topic`:

```python
class VocabCache(Base):
    """One row per English word, shared by all users.

    Definitions are not user-specific, so caching globally means a word is
    generated once for the entire user base. IELTS vocabulary repeats heavily,
    so the hit rate is high and the marginal cost of a lookup trends to zero.
    """

    __tablename__ = "vocab_cache"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False, unique=True, index=True)  # lowercased
    definition_en = Column(Text, nullable=False)
    definition_zh = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    phonetic = Column(String(100), nullable=True)          # IPA, e.g. /ˈæmplɪfaɪ/
    audio_url = Column(String(500), nullable=True)         # self-hosted, /audio/...
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 2: Fix the stale comment** on `Topic.audio_url` (line 114):

```python
    audio_url = Column(String(500), nullable=True)  # self-hosted MP3 under TTS_AUDIO_URL_PREFIX
```

- [ ] **Step 3: Confirm the table is created**

`database.py` calls `Base.metadata.create_all`, so no migration is needed.

Run: `cd backend && python -c "from app.models.models import VocabCache; print(VocabCache.__tablename__)"`
Expected: `vocab_cache`

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/models.py
git commit -m "feat(vocab): add global VocabCache model"
```

---

## Task 2: Lookup service

**Files:** Create `backend/app/services/vocab.py`, Test `backend/tests/test_vocab.py`

- [ ] **Step 1: Write the failing test**

```python
import json

import pytest

from app.services import vocab


def test_parse_returns_all_fields():
    raw = json.dumps({
        "definition_en": "to increase the strength of something",
        "definition_zh": "放大；增强",
        "example": "The hall amplified every footstep.",
        "phonetic": "/ˈæmplɪfaɪ/",
    })
    parsed = vocab.parse_lookup(raw)
    assert parsed["definition_en"].startswith("to increase")
    assert parsed["definition_zh"] == "放大；增强"
    assert parsed["phonetic"] == "/ˈæmplɪfaɪ/"


def test_parse_tolerates_missing_optional_fields():
    parsed = vocab.parse_lookup(json.dumps({"definition_en": "a thing"}))
    assert parsed["definition_en"] == "a thing"
    assert parsed["definition_zh"] is None
    assert parsed["phonetic"] is None


def test_parse_rejects_a_missing_definition():
    with pytest.raises(ValueError):
        vocab.parse_lookup(json.dumps({"phonetic": "/x/"}))


def test_normalise_word():
    assert vocab.normalise("  Amplify  ") == "amplify"
    assert vocab.normalise("RIVER") == "river"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_vocab.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.vocab'`

- [ ] **Step 3: Implement**

```python
"""Vocabulary lookup: definition, IPA, Chinese and self-hosted pronunciation.

Replaces api.dictionaryapi.dev (free, unauthenticated, no SLA) which was called
directly from the browser and whose audio URLs were persisted into topics rows —
meaning an outage there would have retroactively broken saved vocabulary.
"""

import json
import logging

from app.services.ai.llm import chat_json

logger = logging.getLogger(__name__)

LOOKUP_PROMPT = (
    "You are a lexicographer helping Chinese-speaking IELTS students.\n"
    "For the given English word, return JSON with these keys:\n"
    '  "definition_en": a clear one-sentence definition in simple English\n'
    '  "definition_zh": the same meaning in natural Simplified Chinese\n'
    '  "example":       one natural example sentence using the word\n'
    '  "phonetic":      British IPA in slashes, e.g. /ˈæmplɪfaɪ/\n'
    "If a sentence of context is supplied, define the sense used there.\n"
    "No commentary, no pinyin."
)


def normalise(word: str) -> str:
    """Cache key: words are looked up case-insensitively."""
    return word.strip().lower()


def parse_lookup(raw: str) -> dict:
    """Validate the model's JSON. A definition is mandatory; the rest are optional."""
    data = json.loads(raw)
    definition = (data.get("definition_en") or "").strip()
    if not definition:
        raise ValueError("model returned no definition_en")
    return {
        "definition_en": definition,
        "definition_zh": (data.get("definition_zh") or "").strip() or None,
        "example": (data.get("example") or "").strip() or None,
        "phonetic": (data.get("phonetic") or "").strip() or None,
    }


def generate_entry(word: str, context: str | None = None) -> dict:
    """One model call for definition + Chinese + example + IPA."""
    user = f"Word: {word}"
    if context:
        user += f"\nSentence it appeared in: {context}"
    raw = chat_json(
        tier="utility",
        messages=[
            {"role": "system", "content": LOOKUP_PROMPT},
            {"role": "user", "content": user},
        ],
        max_output_tokens=400,
        reasoning_effort="low",
    )
    return parse_lookup(raw)


def synthesize_pronunciation(word: str) -> str | None:
    """British-voice MP3 for the word. Audio is optional — never fail the lookup."""
    try:
        from app.services.tts import synthesize

        return synthesize(word, voice_key="british_female")
    except Exception as e:
        logger.warning("pronunciation synthesis failed for %r: %s", word, e)
        return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_vocab.py -q`
Expected: PASS — 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/vocab.py backend/tests/test_vocab.py
git commit -m "feat(vocab): add lookup service with model + TTS"
```

---

## Task 3: Cached endpoint

**Files:** Modify `backend/app/routers/generate.py`

- [ ] **Step 1: Add the endpoint**, replacing `translate_definition` and its body model:

```python
class DefineWordBody(BaseModel):
    word: str
    context: str | None = None


@router.post("/define-word")
def define_word(
    body: DefineWordBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Definition + Chinese + IPA + self-hosted audio, cached globally by word."""
    key = vocab.normalise(body.word)
    if not key:
        raise HTTPException(status_code=400, detail="word is required")

    cached = db.query(VocabCache).filter(VocabCache.word == key).first()
    if cached:
        return {
            "word": cached.word,
            "definition_en": cached.definition_en,
            "definition_zh": cached.definition_zh,
            "example": cached.example,
            "phonetic": cached.phonetic,
            "audio_url": cached.audio_url,
            "cached": True,
        }

    try:
        entry = vocab.generate_entry(body.word, body.context)
    except Exception as e:
        logger.error("define_word failed for %r: %s", key, e)
        raise HTTPException(status_code=502, detail="lookup unavailable")

    entry["audio_url"] = vocab.synthesize_pronunciation(key)

    row = VocabCache(word=key, **entry)
    db.add(row)
    try:
        db.commit()
    except Exception:
        # Another request cached the same word first — harmless.
        db.rollback()

    return {"word": key, **entry, "cached": False}
```

- [ ] **Step 2: Update imports**

```python
from app.models.models import GeneratedPractice, Topic, User, UserPractice, VocabCache
from app.services import vocab
```

- [ ] **Step 3: Delete `translate_definition`**, its `TranslateDefinitionBody`, and `TRANSLATE_DEFINITION_PROMPT` — `define-word` returns `definition_zh` directly, so the separate call is redundant.

- [ ] **Step 4: Delete the superseded test**

```bash
git rm backend/tests/test_translate_definition.py
```

- [ ] **Step 5: Add endpoint tests** to `backend/tests/test_vocab.py`:

```python
def test_define_word_caches_after_first_call(client, test_user, auth_token, monkeypatch):
    calls = []

    def fake_generate(word, context=None):
        calls.append(word)
        return {"definition_en": "a bank of a river", "definition_zh": "河岸",
                "example": "We sat on the bank.", "phonetic": "/bæŋk/"}

    monkeypatch.setattr(vocab, "generate_entry", fake_generate)
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: "/audio/bank.mp3")

    h = {"Authorization": f"Bearer {auth_token}"}
    first = client.post("/api/generate/define-word", json={"word": "Bank"}, headers=h)
    second = client.post("/api/generate/define-word", json={"word": "bank"}, headers=h)

    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert second.json()["definition_zh"] == "河岸"
    assert len(calls) == 1, "second lookup must not hit the model"


def test_define_word_survives_tts_failure(client, test_user, auth_token, monkeypatch):
    monkeypatch.setattr(vocab, "generate_entry", lambda w, c=None: {
        "definition_en": "x", "definition_zh": None, "example": None, "phonetic": None})
    monkeypatch.setattr(vocab, "synthesize_pronunciation", lambda w: None)

    resp = client.post("/api/generate/define-word", json={"word": "zzz"},
                       headers={"Authorization": f"Bearer {auth_token}"})
    assert resp.status_code == 200
    assert resp.json()["audio_url"] is None


def test_define_word_requires_auth(client):
    assert client.post("/api/generate/define-word", json={"word": "x"}).status_code == 401
```

- [ ] **Step 6: Run the suite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/generate.py backend/tests/
git commit -m "feat(vocab): cached define-word endpoint, retire translate-definition"
```

---

## Task 4: Frontend — one client, three call sites

**Files:** Modify `frontend/src/utils/dictionary.ts`, `useVocabSelection.ts`, `Topics.tsx`, `AIGrammarView.tsx`

- [ ] **Step 1: Replace the parser with an API client** in `frontend/src/utils/dictionary.ts`:

```ts
import api from '../services/api';

export interface WordEntry {
  word: string;
  definition_en: string;
  definition_zh: string | null;
  example: string | null;
  phonetic: string | null;
  audio_url: string | null;
}

/** Look up a word. `context` is the sentence it appeared in, for sense disambiguation. */
export async function lookupWord(word: string, context?: string): Promise<WordEntry> {
  const { data } = await api.post<WordEntry>('/generate/define-word', { word, context });
  return data;
}
```

Verify the import path matches the existing axios instance before writing (the other API helpers in `frontend/src/services/` show the convention).

- [ ] **Step 2: Update `useVocabSelection.ts`** — replace the `fetch` at line 30 and the `parseDictionaryEntry` call:

```ts
      const entry = await lookupWord(selectedWord);
      setDef(entry.definition_en);
      setDefZh(entry.definition_zh || '');
      setPhonetic(entry.phonetic || '');
      setAudioUrl(entry.audio_url || '');
```

The separate `topicsAPI.translateDefinition` call and its `language === 'zh'` branch are deleted — Chinese now arrives in the same response.

- [ ] **Step 3: Update `Topics.tsx`** — replace the `fetch` at line 83 and **delete the duplicate `parseDictionaryEntry` at line 13**, using `entry.definition_en` and `entry.example`.

- [ ] **Step 4: Update `AIGrammarView.tsx`** — replace the `fetch` at line 80 with `lookupWord(word)`, passing the surrounding sentence as `context` where available.

- [ ] **Step 5: Verify no direct calls remain**

Run: `cd frontend && grep -rn "dictionaryapi.dev\|parseDictionaryEntry" src/`
Expected: no output.

- [ ] **Step 6: Build and test**

Run: `cd frontend && npx vitest run && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(vocab): route lookups through the backend, drop duplicate parser"
```

---

## Task 5: Deploy and verify

- [ ] **Step 1:** `git push origin main`; confirm CI and Deploy are both `success`.
- [ ] **Step 2: Verify a cold lookup** — tap a word not looked up before. Expect a definition, Chinese, IPA, and audio that plays from your own domain (`/audio/...`), not an external host.
- [ ] **Step 3: Verify the cache** — look the same word up again and confirm `cached: true`, and that no model call occurs.
- [ ] **Step 4: Verify context disambiguation** — look up "bank" in a river passage and confirm the river sense, not 银行.
- [ ] **Step 5: Confirm the MP3 survives a deploy** — redeploy and re-play the audio, since `deploy.yml` preserves the `audio/` directory.

---

## Follow-ups deliberately excluded

- **Backfilling old `Topic.audio_url` rows** that still point at dictionaryapi.dev. They keep working until that service disappears; regenerating them is a separate migration.
- **Cache eviction / refresh.** Definitions are stable, so entries never expire. If a bad definition is ever cached, deleting the row regenerates it.
