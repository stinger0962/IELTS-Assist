# Speaking Part 3 — Discussion (v0.23.0)

## Context

Parts 1 and 2 are live. Part 3 (Discussion) completes the standalone speaking parts before full test simulation in v0.24.0. Part 3 uses abstract/analytical questions — "Why do you think..." — with longer expected answers (30-60s).

MVP: standalone with pre-generated questions. Adaptive follow-ups linked to Part 2 deferred to v0.24.0.

---

## Question Bank

**`speaking_config.py`** — add `PART3_DISCUSSION_SETS`:

- 30 discussion themes × 4-5 questions = ~140 questions
- Themes: education, technology, environment, health, work, family, travel, media, food, cities, culture, language, money, sport, crime, government, art, science, transport, housing, communication, aging, success, globalization, tradition, nature, entertainment, fashion, equality, innovation
- Each theme:
  ```python
  {"id": "p3_education", "topic_title": "Education & Learning", "questions": [
      "Why do you think some people prefer self-study over classroom learning?",
      "How has technology changed the way people learn?",
      "Do you think the education system in most countries needs to change?",
      "What skills do you think are most important for young people to learn today?",
  ]}
  ```
- `generate_metadata_part3(avoid_topics)` picks 1 random theme, returns exercise dict
- No GPT needed — instant pool seeding

## Content JSON (GeneratedPractice)

```json
{
    "meta": { "module": "speaking_part3", "topic": "Education & Learning" },
    "topics": [
        { "area": "Education & Learning", "questions": ["Why do you think...", "..."] }
    ]
}
```

Note: uses same `topics` array format as Part 1, but with only 1 entry. This lets the frontend reuse the same data structure.

## Pool Balance

`_seed_speaking_pool` rotates across all 3 parts:
- Count existing Part 1 / Part 2 / Part 3 in pool
- Seed whichever has fewest
- Target: ~1/3 each

## Frontend — `AISpeakingPart3View.tsx`

Same continuous recording pattern as Part 1 but:
- 4-5 questions (not 12)
- Single theme (no topic transitions)
- Intro text: "Part 3: Discussion — The examiner will ask analytical questions. Give detailed answers of 30-60 seconds each."
- Question card styled for analytical tone
- Same processing + results as Part 1

## Practice.tsx Card Display

```
Part 1: "Interview · 3 topics"
Part 2: "Long Turn · {domain}"
Part 3: "Discussion · {theme}"
```

Route to correct view based on `meta.module`.

## Reuse

- Same `submit-ai-speaking` endpoint
- Same `SpeakingGrader` (same 4 criteria)
- Same progress tracking (speaking-insights includes all parts)
- Same pronunciation analysis option

## Files

| File | Change |
|------|--------|
| `backend/app/services/ai/speaking_config.py` | Add PART3_DISCUSSION_SETS + generate_metadata_part3() |
| `backend/app/routers/speaking.py` | Update _seed_speaking_pool for 3-way balance |
| `frontend/src/components/practice/AISpeakingPart3View.tsx` | CREATE — discussion recording flow |
| `frontend/src/pages/Practice.tsx` | Route Part 3 + card label |

## Verification

1. Backend tests pass
2. Frontend build passes
3. Speaking list shows mix of Part 1, Part 2, Part 3 cards
4. Part 3: tap → 4-5 questions → record → submit → results
5. Parts 1 and 2 still work unchanged
