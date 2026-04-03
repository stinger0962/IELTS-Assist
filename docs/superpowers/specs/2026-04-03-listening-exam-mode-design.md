# Full Listening Test — Exam Mode Design

## Goal
Build a full IELTS Listening exam simulation with 4 sequential audio sections, 40 questions, progressive difficulty, and VIP-gated access.

## Architecture
Orchestrator layer on top of existing listening generator. Calls the existing 3-step pipeline (metadata → transcript → questions) + TTS 4 times with different format hints and difficulty profiles. Pre-generated via daily cron (~6 min generation time). Reuses VIP gate, recent exams, and review patterns from reading exam.

---

## 1. Difficulty Profiles

| Section | Format | Category | Transcript | Speed | Questions |
|---|---|---|---|---|---|
| 1 | conversation | daily_life | 400-500w | normal | 10 |
| 2 | monologue | public_info | 500-600w | normal | 10 |
| 3 | discussion | workplace/academic | 600-700w | slightly faster | 10 |
| 4 | lecture | academic | 700-900w | normal | 10 |

Sections 3-4: more complex vocabulary, abstract topics, harder question types.

## 2. Data Model

```json
{
  "meta": {
    "module": "listening_full_test",
    "topic": "Full Listening Test — gym enrollment, museum tour, research discussion, climate lecture",
    "total_questions": 40,
    "time_limit_minutes": 30
  },
  "sections": [
    {
      "section_number": 1,
      "format": "conversation",
      "difficulty_profile": { "text_complexity": 2, "inference_demand": 1, "question_difficulty": 2 },
      "audio_url": "/audio/exam_lt_xxx_s1.mp3",
      "transcript": "Speaker A: ...\nSpeaker B: ...",
      "questions": { "groups": [...] },
      "question_count": 10
    },
    { "section_number": 2, ... },
    { "section_number": 3, ... },
    { "section_number": 4, ... }
  ]
}
```

## 3. Generation Pipeline

1. **Blueprint** (no GPT): pick 4 topics from different categories, assign format + difficulty
2. **Generate Section 1**: metadata → transcript → questions → TTS audio (conversation, daily_life)
3. **Generate Section 2**: metadata → transcript → questions → TTS audio (monologue, public_info)
4. **Generate Section 3**: metadata → transcript → questions → TTS audio (discussion, academic)
5. **Generate Section 4**: metadata → transcript → questions → TTS audio (lecture, academic)
6. **Validate**: check 4 sections, 10 questions each, all audio files exist
7. **Assemble** into single `GeneratedPractice` with `module: "listening_full_test"`

Steps 2-5 run sequentially (~90s each = ~6 min total). Daily cron generates 1 exam.

## 4. Backend

### New files
- `services/ai/listening_exam.py` — orchestrator: `generate_listening_exam()`, section profiles, validator
- `routers/listening_exam.py` — `POST /submit-ai-listening-exam` endpoint

### Modified files
- `routers/generate.py` — daily cron adds 1 listening exam generation
- `routers/listening.py` — filter `listening_full_test` from daily-listening for non-VIP
- `routers/reading_exam.py` — `GET /recent-exams` already supports `?skill=listening`

### Submit endpoint
Receives: `{ practice_id, sections: [{ section_number, answers: {...} }], time_taken_seconds }`
Scores same as reading exam: per-section breakdown, question-type stats, band mapping.

Band mapping (40 questions):
- 37-40: 8.5-9.0
- 32-36: 7.5-8.0
- 27-31: 7.0
- 23-26: 6.5
- 18-22: 6.0
- 14-17: 5.5
- 10-13: 5.0
- <10: 4.0-4.5

## 5. Frontend

### New file
- `components/practice/AIListeningFullTestView.tsx`

### State machine
```
intro → section_1_prep → section_1_play → section_2_prep → section_2_play →
section_3_prep → section_3_play → section_4_prep → section_4_play →
review → confirm → processing → results
```

### Each section flow
1. **Prep phase** (30s): "Section N — Read the questions" countdown, questions visible, audio not playing
2. **Play phase**: Audio auto-plays, questions visible, user answers while listening
3. **Post-audio** (30s): Finalize answers, then auto-advance to next section

### Results page
Same design as reading exam:
- Overall band + score
- Clickable section cards with "Review →"
- Question-type breakdown
- Review mode: Transcript tab (replaces Passage tab) + Questions tab
- Finish button

### Practice.tsx changes
- Exam tab for listening: show full test cards for VIP, VipGate for free users
- Recent exams section (reuse existing `getRecentExams('listening')`)

## 6. MVP vs V2

### MVP (v0.29.0)
- 4 sections × 10 questions = 40 total
- Sequential audio, no replay during exam
- 30s question preview before each section
- Results with section breakdown
- Review mode with transcript + questions tabs
- VIP gated, 1 exam/day via cron

### V2 (pipeline)
- Allow one replay per section
- Timestamp-linked transcript in review (lyrics mode)
- Audio playback speed control in review
- Difficulty analytics per dimension
