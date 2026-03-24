# Speaking Part 1 — Interview (v0.22.0)

## Context

Part 2 (Long Turn) is live. Part 1 (Interview) is the most common IELTS speaking format — examiner asks ~12 short questions across 3 topic areas. User answers each in 15-30s. This is a multi-turn conversational flow, unlike Part 2's single recording.

Design principle: reuse as much existing infrastructure as possible (same submit endpoint, same grader, same progress tracking).

---

## Question Bank

**`speaking_config.py`** — add `PART1_TOPIC_SETS` alongside `PART2_CUE_CARDS`:

- 30 topic areas × 4 questions = 120 questions total
- Topics: hometown, family, work/study, food, weather, hobbies, music, sports, transport, shopping, friends, holidays, animals, colors, flowers, daily routine, sleep, social media, reading, movies, photography, art, science, clothes, gifts, neighbors, patience, concentration, memories, plans
- Each topic set:
  ```python
  { "id": "p1_hometown", "topic_title": "Hometown", "questions": [
      "Where is your hometown?",
      "What do you like most about your hometown?",
      "Has your hometown changed much in recent years?",
      "Would you like to live there in the future?"
  ]}
  ```
- `generate_metadata_part1(avoid_topics)` picks 3 random topic areas, returns bundled exercise
- No GPT needed — instant pool seeding

## Content JSON (GeneratedPractice)

```json
{
    "meta": { "module": "speaking_part1", "topic": "Hometown, Food, Daily Routine" },
    "topics": [
        { "area": "Hometown", "questions": ["Where is your hometown?", "..."] },
        { "area": "Food", "questions": ["..."] },
        { "area": "Daily Routine", "questions": ["..."] }
    ]
}
```

## Pool Balance

- `_seed_speaking_pool` alternates Part 1 / Part 2 — whichever has fewer gets seeded
- Target: 50/50 split at all times
- Future daily cron: 1 Part 1 + 1 Part 2 per day

## Frontend — `AISpeakingPart1View.tsx`

Multi-turn conversational flow:

```
intro → Q1 → Q2 → ... → Q12 → processing → results
```

Each question step:
1. Topic area header shown ("Let's talk about your hometown")
2. Question text displayed (large, readable)
3. Recording auto-starts (mic activates, red dot indicator)
4. User speaks 15-30s, taps "Next Question"
5. Audio chunk saved to array
6. Between topic areas: transition message ("Now let's talk about food")
7. After Q12: concatenate all audio chunks into one blob

UI layout (mobile-first):
- Top: progress indicator (Q3/12) + topic area label
- Center: question text
- Bottom: recording indicator + "Next Question" button
- Minimal — no clutter

## Submit Flow

Reuse existing `POST /submit-ai-speaking`:
- Frontend concatenates 12 audio chunks → single blob
- Backend: Whisper transcribes → GPT-4o grades (same grader)
- GPT receives question list as context (instead of cue card bullets)
- Same 4 criteria, same results UI, same progress tracking

## Grading

Reuse `SpeakingGrader` — pass questions as context instead of cue card:
```python
cue_card = {
    "topic_line": "Part 1 Interview: Hometown, Food, Daily Routine",
    "bullets": ["Where is your hometown?", "What do you like about food?", ...],
}
```

Same 4 criteria output. Same results page. Same pronunciation analysis option.

## Practice.tsx Card Display

Differentiate by `meta.module`:
- Part 1: "Interview · 3 topics"
- Part 2: "Long Turn · {domain}"

Route to `AISpeakingPart1View` or `AISpeakingExerciseView` based on module.

## Types

Extend `AISpeakingPractice`:
```typescript
export interface AISpeakingPractice {
  practice_db_id: number;
  meta: { module: string; domain?: string; topic: string };
  cue_card?: SpeakingCueCard;        // Part 2 only
  topics?: { area: string; questions: string[] }[];  // Part 1 only
  cue_card_metadata?: Record<string, any>;
}
```

## Files

| File | Change |
|------|--------|
| `backend/app/services/ai/speaking_config.py` | Add PART1_TOPIC_SETS + generate_metadata_part1() |
| `backend/app/routers/speaking.py` | Modify _seed_speaking_pool for 50/50 balance |
| `frontend/src/components/practice/AISpeakingPart1View.tsx` | CREATE — multi-turn recording |
| `frontend/src/pages/Practice.tsx` | Route Part 1 vs Part 2 to correct view |
| `frontend/src/types/index.ts` | Add topics field to AISpeakingPractice |

## Verification

1. Backend tests pass
2. Frontend build passes
3. Dashboard → Practice → Speaking list shows mix of Part 1 and Part 2 cards
4. Part 1: tap → 12 questions → record each → submit → grading results
5. Part 2: unchanged, still works
6. Progress page shows both Part 1 and Part 2 sessions
