# Reading Exam Mode — Design Spec

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement.

**Goal:** Full-length IELTS-style reading exam simulation — 3 passages, 30 questions (MVP), 60-min timer, progressive difficulty, delayed feedback, VIP-only access.

**Architecture:** Reusable exam framework built as an orchestration layer on top of existing reading generator. Same pattern applies to listening (v0.29.0), writing (v0.30.0). Speaking already done (v0.24.0).

---

## 1. Architecture — Three Layers

```
Exam Orchestrator (new: reading_exam.py)
  ↓ calls 3×
Section Generator (existing: practice_generator.py, modified to accept difficulty_profile)
  ↓
Validator (new: lightweight, in orchestrator)
```

- **Exam Orchestrator**: picks 3 topics from different domains, assigns difficulty profiles, calls the existing 2-step pipeline 3 times, validates, assembles into one GeneratedPractice.
- **Section Generator**: existing `generate_passage()` → `generate_questions()` pipeline, extended to accept a `difficulty_profile` dict that modifies the GPT prompts.
- **Validator**: checks question counts, answer key consistency, topic diversity, passage length balance. MVP: reject-and-retry on failure. V2: repair pass.

---

## 2. Difficulty Model — 3 Composite Dimensions

Each dimension rated 1–5:

| Dimension | Components | Controls |
|---|---|---|
| **Text complexity** | Vocabulary level, sentence length, information density | How hard the passage is to read |
| **Inference demand** | Abstractness, paraphrase distance, implicit reasoning | How much the reader must infer beyond surface text |
| **Question difficulty** | Distractor strength, option similarity, heading ambiguity | How tricky the questions themselves are |

### Section Profiles

| | Section 1 | Section 2 | Section 3 |
|---|---|---|---|
| Text complexity | 2 | 3 | 4–5 |
| Inference demand | 1–2 | 3 | 4–5 |
| Question difficulty | 2 | 3 | 4 |
| Topic style | Factual, descriptive | Analytical, comparative | Abstract, argumentative |
| Passage length | 600–650 words | 650–700 words | 650–750 words |
| Questions | 10 (MVP) / 13 (V2) | 10 (MVP) / 13 (V2) | 10 (MVP) / 14 (V2) |
| Question types | T/F/NG, completion, MCQ | Matching headings, summary, MCQ | Matching info, Y/N/NG, short answer |

---

## 3. Data Model

### GeneratedPractice.content JSON

```json
{
  "meta": {
    "module": "reading_full_test",
    "topic": "Full Reading Test — Environment, Technology, Philosophy",
    "total_questions": 30,
    "time_limit_minutes": 60,
    "version": "v1"
  },
  "sections": [
    {
      "section_number": 1,
      "difficulty_profile": {
        "text_complexity": 2,
        "inference_demand": 1,
        "question_difficulty": 2
      },
      "meta": {
        "topic": "Urban Green Spaces",
        "domain": "environment",
        "word_count": 640
      },
      "passage": {
        "title": "The Role of Urban Green Spaces in Modern Cities",
        "content": "..."
      },
      "questions": {
        "groups": [
          {
            "type": "true_false_not_given",
            "instructions": "Do the following statements agree with the information in the passage?",
            "items": [...],
            "answers": [...]
          },
          {
            "type": "sentence_completion",
            "instructions": "Complete the sentences below.",
            "items": [...],
            "answers": [...]
          }
        ]
      }
    },
    { "section_number": 2, "..." : "..." },
    { "section_number": 3, "..." : "..." }
  ]
}
```

Each section's `questions.groups` uses the **exact same format** as existing reading exercises — no new question format.

### User submission (UserPractice.user_answers)

```json
{
  "sections": [
    {
      "section_number": 1,
      "answers": { "q_0_0": "TRUE", "q_0_1": "FALSE", "q_1_0": "urban parks" }
    },
    { "section_number": 2, "answers": { ... } },
    { "section_number": 3, "answers": { ... } }
  ],
  "time_taken_seconds": 3245,
  "submitted_at": "2026-03-30T12:00:00Z"
}
```

---

## 4. Generation Pipeline

```
1. Blueprint (no GPT)
   - Pick 3 topics from different domains (using reading_config.generate_metadata)
   - Assign difficulty profiles for sections 1, 2, 3
   - Assign question type mix per section

2. Generate Section 1 (2 GPT calls: passage → questions)
   - Inject difficulty_profile into passage prompt
   - Inject question type requirements into questions prompt

3. Generate Section 2 (2 GPT calls)
4. Generate Section 3 (2 GPT calls)

5. Validate
   - Total question count == target (30)
   - Each section has correct number of questions
   - No duplicate topics across sections
   - All answer keys present and non-empty
   - Passage word counts within range

6. If invalid → reject affected section → regenerate (max 2 retries)
   V2: repair pass instead of full regeneration

7. Assemble into single GeneratedPractice record
   - skill = "reading"
   - topic = "Full Reading Test — {topic1}, {topic2}, {topic3}"
   - content = full JSON above
```

**Total GPT calls:** 6 (2 per section) + potential retries
**Estimated time:** 2–3 minutes
**Estimated cost:** ~$0.15–0.25 per exam

---

## 5. Prompt Modifications

### Existing passage generator — add difficulty_profile

Inject into the system prompt:

```
Difficulty profile for this section:
- Text complexity: {text_complexity}/5 — {"Use simple, concrete vocabulary" if 1-2 else "Use academic, specialized vocabulary" if 4-5}
- Inference demand: {inference_demand}/5 — {"State information directly" if 1-2 else "Require readers to infer meaning from context" if 4-5}

Topic style: {topic_style}
Target word count: {target_word_count}
```

### Existing question generator — add type requirements

Inject into the prompt:

```
Generate exactly {question_count} questions for this passage.
Required question types for this section:
{question_type_requirements}

Difficulty level: {question_difficulty}/5
{"Use straightforward distractors" if 1-2 else "Use subtle, closely-related distractors that require careful reading" if 4-5}
```

### No new prompts needed — just parameter injection into existing prompts.

---

## 6. Scoring & Analytics

### Raw score → Band mapping (30 questions)

| Correct | Band |
|---|---|
| 28–30 | 8.5–9.0 |
| 25–27 | 7.5–8.0 |
| 22–24 | 7.0 |
| 19–21 | 6.5 |
| 15–18 | 6.0 |
| 12–14 | 5.5 |
| 9–11 | 5.0 |
| <9 | 4.0–4.5 |

V2 (40 questions): use official IELTS band table.

### Per-section breakdown

```json
{
  "overall": { "correct": 24, "total": 30, "band": 7.0 },
  "sections": [
    { "section": 1, "correct": 9, "total": 10 },
    { "section": 2, "correct": 8, "total": 10 },
    { "section": 3, "correct": 7, "total": 10 }
  ],
  "question_types": [
    { "type": "true_false_not_given", "correct": 5, "total": 7, "accuracy": 71 },
    { "type": "matching_headings", "correct": 3, "total": 5, "accuracy": 60 }
  ],
  "weakness_diagnosis": "Matching headings and inference-heavy questions are your weakest areas."
}
```

---

## 7. User Role System (new, reusable across all skills)

### Backend

Add `role` column to `User` model:
- `'free'` (default)
- `'vip'`

Migration: `ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'free'`

Endpoint filter: `_available_reading_for_user` excludes `reading_full_test` for non-VIP users.

### Frontend

Exam tab behavior:
- **VIP user**: shows full test cards (same as speaking full test)
- **Free user**: shows lock icon + "VIP Feature — Unlock full-length exam simulations"

VIP gate component: `<VipGate skill="reading" />` — reusable across all skills.

---

## 8. Pool & Cron

- Daily cron adds 1 `reading_full_test` per day (server-wide, not per-user)
- Generation runs at midnight UTC alongside existing cron jobs
- Pool target: keep at least 2 full tests available
- Each exam is ~30KB of JSON (3 passages + 30 questions)

---

## 9. API Endpoints

### Generate (cron only, not user-facing)

Internal function in `reading_exam.py`:
```python
def generate_reading_exam(db: Session) -> GeneratedPractice:
    """Generate one full reading exam. Called by daily cron."""
```

### Submit

```
POST /generate/submit-ai-reading-exam
Body: { "practice_id": 123, "sections": [...answers...], "time_taken_seconds": 3245 }
Response: { "overall": {...}, "sections": [...], "question_types": [...], "weakness_diagnosis": "..." }
```

### Daily (existing pattern)

Full test cards appear in `GET /generate/daily-reading` response, filtered by VIP role.

---

## 10. Frontend — AIReadingFullTestView.tsx

### State machine

```
intro → exam → confirm_submit → processing → results
```

### Exam screen

- **Top bar**: Section tabs [1] [2] [3] + 60-min countdown timer
- **Main area**:
  - Desktop: passage left, questions right (split view)
  - Mobile: passage then questions (scroll)
- **Answer persistence**: single state object `{ section_1: { q_0_0: "TRUE" }, section_2: {...} }`
- **Free navigation**: user can jump between sections anytime
- **Submit button**: bottom of section 3, triggers confirmation dialog
- **Auto-submit**: at 60 min with warning at 55 min

### Results screen

- Confetti + band count-up animation
- Overall band + correct/total
- Per-section cards (Section 1: 9/10, Section 2: 8/10, Section 3: 7/10)
- Question-type accuracy breakdown
- Weakness diagnosis text
- Expandable: each question with correct/wrong + explanation
- "Finish" button returns to practice list

---

## 11. MVP vs V2

### MVP (v0.28.0)

- [ ] User role field (`free`/`vip`) + migration
- [ ] VIP gate component (reusable)
- [ ] Reading exam orchestrator (reading_exam.py)
- [ ] Difficulty profile injection into existing generator
- [ ] Validator (reject-and-retry)
- [ ] Daily cron: 1 reading exam/day
- [ ] Submit endpoint with scoring
- [ ] Frontend: AIReadingFullTestView.tsx
- [ ] Exam tab: VIP gate for free users, full test cards for VIP
- [ ] 3 sections × 10 questions = 30 total
- [ ] 600–700 word passages

### V2 (future)

- [ ] 40 questions (13-14 per passage)
- [ ] 800–1000 word passages
- [ ] Repair pass validation (instead of reject-retry)
- [ ] Per-dimension difficulty analytics in results
- [ ] Historical exam comparison (trend across exams)
- [ ] Full-length exams for listening (v0.29.0), writing (v0.30.0)
- [ ] Subscription/payment system for VIP access

### Pipeline (noted)

- Listening full test: same framework, 4 sections, 30 min timer
- Writing full test: Task 1 + Task 2, 60 min timer
- Unified "Full IELTS" mode: all 4 skills in sequence (v0.31.0+)

---

## 12. Pitfalls to Avoid

**#1 most important**: Don't let the exam orchestrator become a separate generation system. It must call the existing reading pipeline with parameters — not duplicate it. If we need a new prompt, we modify the existing one to accept an optional `difficulty_profile`, not create a parallel prompt.

**#2**: Don't over-engineer validation for MVP. Simple count checks + answer key presence is enough. Semantic validation (are answers actually correct?) is a V2 concern.

**#3**: Pre-generate, don't generate on demand. Users should never wait 3 minutes for an exam to generate.
