# Reading Exam Mode Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Full-length IELTS reading exam with 3 passages, 30 questions, 60-min timer, progressive difficulty, VIP-only access.

**Architecture:** Exam orchestrator layer on top of existing reading generator. User role field for VIP gating. Daily cron generates 1 exam server-wide. Frontend: passage tabs with free navigation, countdown timer, delayed feedback.

**Tech Stack:** FastAPI, SQLAlchemy, OpenAI GPT-4o-mini, React/TypeScript, existing reading_config + practice_generator.

**Spec:** `docs/superpowers/specs/2026-03-30-reading-exam-mode-design.md`

---

## File Structure

### Backend — Create
- `backend/app/services/ai/reading_exam.py` — Exam orchestrator: blueprint, generate 3 sections, validate, assemble
- `backend/app/routers/reading_exam.py` — Submit endpoint for full reading exam

### Backend — Modify
- `backend/app/models/models.py` — Add `role` column to User
- `backend/app/database.py` — Add migration for `role` column
- `backend/app/services/ai/practice_generator.py` — Accept `difficulty_profile` parameter
- `backend/app/routers/reading.py` — Filter full tests by VIP role in daily-reading
- `backend/app/routers/generate.py` — Add reading exam to daily cron
- `backend/app/main.py` — Include reading_exam router

### Frontend — Create
- `frontend/src/components/practice/AIReadingFullTestView.tsx` — Full exam UI
- `frontend/src/components/VipGate.tsx` — Reusable VIP lock component

### Frontend — Modify
- `frontend/src/types/index.ts` — Add ReadingExam types, User role
- `frontend/src/api/index.ts` — Add submitReadingExam API method
- `frontend/src/pages/Practice.tsx` — Show VIP gate or full test cards in Exam tab

---

## Chunk 1: User Role System

### Task 1: Add role column to User model

**Files:**
- Modify: `backend/app/models/models.py:16-37`
- Modify: `backend/app/database.py`

- [ ] **Step 1: Add role column to User model**

In `backend/app/models/models.py`, add after line 26 (`preferred_language`):

```python
    role = Column(String(20), default="free")  # "free" or "vip"
```

- [ ] **Step 2: Add migration in database.py**

In `backend/app/database.py`, find `init_db()` function and add migration:

```python
# In the inline migrations section:
try:
    conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'free'"))
    conn.commit()
except Exception:
    conn.rollback()
```

- [ ] **Step 3: Apply migration on VPS**

```bash
ssh -i ~/.ssh/ielts_assist_deploy root@152.42.251.169 \
  "psql postgresql://ielts_user:ielts_pass_2024@localhost:5432/ielts_assist \
   -c \"ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'free'\""
```

- [ ] **Step 4: Update User type in frontend**

In `frontend/src/types/index.ts`, add `role` to User interface:

```typescript
// In the User interface, add:
role: string;  // "free" | "vip"
```

- [ ] **Step 5: Set test user as VIP for testing**

```bash
ssh -i ~/.ssh/ielts_assist_deploy root@152.42.251.169 \
  "psql postgresql://ielts_user:ielts_pass_2024@localhost:5432/ielts_assist \
   -c \"UPDATE users SET role = 'vip' WHERE email = 'test@123.com'\""
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/models.py backend/app/database.py frontend/src/types/index.ts
git commit -m "feat: add user role field (free/vip) for exam access gating"
```

---

### Task 2: VIP Gate Component

**Files:**
- Create: `frontend/src/components/VipGate.tsx`

- [ ] **Step 1: Create VipGate component**

```tsx
import { Sparkles, Lock } from 'lucide-react';

interface VipGateProps {
  skillName: string;
}

export default function VipGate({ skillName }: VipGateProps) {
  return (
    <>
      <div className="vip-gate">
        <div className="vip-icon"><Lock size={32} /></div>
        <h3>Full {skillName} Test</h3>
        <p>Full-length IELTS exam simulations are a VIP feature.</p>
        <div className="vip-badge"><Sparkles size={14} /> VIP</div>
      </div>
      <style>{`
        .vip-gate { text-align: center; padding: var(--spacing-2xl) var(--spacing-md); }
        .vip-icon { margin-bottom: var(--spacing-md); color: var(--color-text-secondary); opacity: 0.5; }
        .vip-gate h3 { font-size: 1.1rem; color: var(--color-text-primary); margin-bottom: var(--spacing-xs); }
        .vip-gate p { font-size: 0.85rem; color: var(--color-text-secondary); margin-bottom: var(--spacing-md); line-height: 1.5; }
        .vip-badge { display: inline-flex; align-items: center; gap: 4px; background: linear-gradient(135deg, #F59E0B, #D97706); color: #fff; padding: 6px 16px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }
      `}</style>
    </>
  );
}
```

- [ ] **Step 2: Wire VipGate into Practice.tsx Exam tab**

In `frontend/src/pages/Practice.tsx`, find the exam mode section. Import VipGate and the user store:

```tsx
import VipGate from '../components/VipGate';
import { useAppStore } from '../store';
```

In the Practice component, add:
```tsx
const { user } = useAppStore();
const isVip = user?.role === 'vip';
```

Replace the existing exam mode section — for reading/listening/grammar/writing, show VipGate if not VIP:

```tsx
// In the exam mode render:
{activeSkill === 'speaking' ? (
  // ... existing speaking full test code ...
) : isVip ? (
  // Show full test cards for VIP (reading exam cards will appear here later)
  <p className="empty-list">No full tests available yet.</p>
) : (
  <VipGate skillName={activeTab.label} />
)}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/VipGate.tsx frontend/src/pages/Practice.tsx
git commit -m "feat: VIP gate component for exam mode access control"
```

---

## Chunk 2: Reading Exam Orchestrator

### Task 3: Modify practice_generator to accept difficulty_profile

**Files:**
- Modify: `backend/app/services/ai/practice_generator.py:212-255`

- [ ] **Step 1: Update generate_practice signature**

Add `difficulty_profile` parameter:

```python
def generate_practice(self, topic_hint: str = "", avoid_topics: list[str] | None = None, difficulty_profile: dict | None = None) -> dict:
```

- [ ] **Step 2: Inject difficulty into passage prompt**

In `_generate_passage()`, add difficulty context to the system message when `difficulty_profile` is provided. Pass it through from `generate_practice`:

```python
# In generate_practice, pass difficulty_profile to _generate_passage:
passage_data = self._generate_passage(metadata, difficulty_profile=difficulty_profile)

# In _generate_passage signature:
def _generate_passage(self, metadata: dict, difficulty_profile: dict | None = None) -> dict | None:

# Before the API call, build difficulty instruction:
difficulty_instruction = ""
if difficulty_profile:
    tc = difficulty_profile.get("text_complexity", 3)
    id_ = difficulty_profile.get("inference_demand", 3)
    difficulty_instruction = f"""
Difficulty profile:
- Text complexity: {tc}/5 — {"Use simple, concrete vocabulary and short sentences" if tc <= 2 else "Use academic vocabulary, complex sentence structures, and dense information" if tc >= 4 else "Use moderate academic vocabulary"}
- Inference demand: {id_}/5 — {"State information directly and explicitly" if id_ <= 2 else "Require readers to infer meaning, use implicit reasoning and heavy paraphrasing" if id_ >= 4 else "Mix explicit and implicit information"}
"""

# Inject into system message:
system_msg = "You are an expert IELTS passage writer. Generate valid JSON only." + difficulty_instruction
```

- [ ] **Step 3: Inject difficulty into questions prompt**

Similarly pass `difficulty_profile` to `_generate_questions()` and add question difficulty context:

```python
# In _generate_questions, add:
if difficulty_profile:
    qd = difficulty_profile.get("question_difficulty", 3)
    difficulty_note = f"\nQuestion difficulty: {qd}/5. " + (
        "Use straightforward distractors and direct answer matching." if qd <= 2
        else "Use subtle, closely-related distractors that require careful reading and inference." if qd >= 4
        else "Use moderately challenging distractors."
    )
    # Append to the user prompt
```

- [ ] **Step 4: Run existing tests to ensure no regression**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai/practice_generator.py
git commit -m "feat: practice_generator accepts difficulty_profile for exam sections"
```

---

### Task 4: Build Reading Exam Orchestrator

**Files:**
- Create: `backend/app/services/ai/reading_exam.py`

- [ ] **Step 1: Create reading_exam.py**

```python
"""Reading Exam Orchestrator.

Generates a full IELTS-style reading exam: 3 sections with progressive difficulty.
Calls the existing practice_generator 3 times with different difficulty profiles.
"""
import json
import logging
from datetime import datetime

from app.services.ai.practice_generator import PracticeGenerator
from app.services.ai.reading_config import generate_metadata

logger = logging.getLogger(__name__)

# Section difficulty presets
SECTION_PROFILES = [
    {
        "section_number": 1,
        "text_complexity": 2,
        "inference_demand": 1,
        "question_difficulty": 2,
        "topic_style": "factual, descriptive",
        "target_questions": 10,
    },
    {
        "section_number": 2,
        "text_complexity": 3,
        "inference_demand": 3,
        "question_difficulty": 3,
        "topic_style": "analytical, comparative",
        "target_questions": 10,
    },
    {
        "section_number": 3,
        "text_complexity": 4,
        "inference_demand": 4,
        "question_difficulty": 4,
        "topic_style": "abstract, argumentative",
        "target_questions": 10,
    },
]


def generate_reading_exam(avoid_topics: list[str] | None = None) -> dict | None:
    """Generate a full reading exam with 3 sections.

    Returns the complete exam content dict, or None if generation fails.
    """
    generator = PracticeGenerator()
    used_topics = list(avoid_topics or [])
    sections = []

    for profile in SECTION_PROFILES:
        section = _generate_section(generator, profile, used_topics)
        if not section:
            logger.error(f"[ReadingExam] Failed to generate section {profile['section_number']}")
            return None
        sections.append(section)
        # Track used topic to avoid repetition
        topic = section.get("meta", {}).get("topic", "")
        if topic:
            used_topics.append(topic)

    # Validate the assembled exam
    if not _validate_exam(sections):
        logger.error("[ReadingExam] Validation failed")
        return None

    # Assemble
    topics_str = ", ".join(s["meta"]["topic"] for s in sections)
    total_q = sum(s["question_count"] for s in sections)

    return {
        "meta": {
            "module": "reading_full_test",
            "topic": f"Full Reading Test — {topics_str}",
            "total_questions": total_q,
            "time_limit_minutes": 60,
            "version": "v1",
        },
        "sections": sections,
    }


def _generate_section(generator: PracticeGenerator, profile: dict, avoid_topics: list[str]) -> dict | None:
    """Generate one exam section using the existing practice generator."""
    difficulty_profile = {
        "text_complexity": profile["text_complexity"],
        "inference_demand": profile["inference_demand"],
        "question_difficulty": profile["question_difficulty"],
    }

    for attempt in range(3):
        practice = generator.generate_practice(
            avoid_topics=avoid_topics,
            difficulty_profile=difficulty_profile,
        )
        if not practice:
            continue

        # Count questions
        groups = practice.get("questions", {}).get("groups", [])
        q_count = sum(len(g.get("answers", g.get("items", []))) for g in groups)

        return {
            "section_number": profile["section_number"],
            "difficulty_profile": difficulty_profile,
            "meta": practice.get("meta", {}),
            "passage": practice.get("passage", {}),
            "questions": practice.get("questions", {}),
            "question_count": q_count,
        }

    return None


def _validate_exam(sections: list[dict]) -> bool:
    """Lightweight validation for assembled exam."""
    if len(sections) != 3:
        return False

    # Check each section has questions
    for s in sections:
        if s.get("question_count", 0) < 5:
            logger.warning(f"[ReadingExam] Section {s['section_number']} has only {s.get('question_count')} questions")
            return False

    # Check topic diversity (no duplicate topics)
    topics = [s["meta"].get("topic", "") for s in sections]
    if len(set(topics)) < 3:
        logger.warning(f"[ReadingExam] Duplicate topics: {topics}")
        return False

    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/ai/reading_exam.py
git commit -m "feat: reading exam orchestrator — 3-section progressive difficulty"
```

---

### Task 5: Add reading exam to daily cron + submit endpoint

**Files:**
- Modify: `backend/app/routers/generate.py:37-62` — Add reading exam to cron
- Create: `backend/app/routers/reading_exam.py` — Submit endpoint
- Modify: `backend/app/main.py` — Include router
- Modify: `backend/app/routers/reading.py` — Filter full tests by VIP

- [ ] **Step 1: Add reading exam generation to daily cron**

In `backend/app/routers/generate.py`, after the reading exercises section (~line 62), add:

```python
# Full reading exam (1 per day, server-wide)
from app.services.ai.reading_exam import generate_reading_exam
logger.info("Daily generation: adding 1 full reading exam")
try:
    exam = generate_reading_exam(avoid_topics=reading_avoid)
    if exam:
        db.add(GeneratedPractice(
            skill="reading",
            topic=exam["meta"]["topic"],
            content=json.dumps(exam),
            is_validated=True,
            generated_date=datetime.utcnow(),
        ))
        db.commit()
        logger.info("Daily reading exam generation complete")
    else:
        logger.warning("Daily reading exam generation failed — no exam produced")
except Exception as e:
    logger.error(f"Daily reading exam generation error: {e}")
```

- [ ] **Step 2: Create reading_exam router with submit endpoint**

Create `backend/app/routers/reading_exam.py`:

```python
"""Reading exam endpoints — submit + scoring."""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

BAND_MAP_30 = [
    (28, 8.5), (25, 7.5), (22, 7.0), (19, 6.5),
    (15, 6.0), (12, 5.5), (9, 5.0), (0, 4.0),
]


def _score_to_band(correct: int, total: int = 30) -> float:
    for threshold, band in BAND_MAP_30:
        if correct >= threshold:
            return band
    return 4.0


class ReadingExamSubmission(BaseModel):
    practice_id: int
    sections: list[dict]  # [{"section_number": 1, "answers": {"q_0_0": "TRUE", ...}}, ...]
    time_taken_seconds: int


@router.post("/submit-ai-reading-exam")
def submit_reading_exam(
    body: ReadingExamSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a full reading exam submission."""
    up = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == body.practice_id,
        UserPractice.submitted_at.is_(None),
    ).first()
    if not up:
        raise HTTPException(404, "Practice not found or already submitted")

    gp = db.query(GeneratedPractice).get(up.practice_id)
    content = json.loads(gp.content)
    exam_sections = content.get("sections", [])

    # Score each section
    section_results = []
    total_correct = 0
    total_questions = 0
    question_type_stats = {}

    for exam_section in exam_sections:
        sec_num = exam_section["section_number"]
        # Find user answers for this section
        user_section = next((s for s in body.sections if s.get("section_number") == sec_num), None)
        user_answers = user_section.get("answers", {}) if user_section else {}

        groups = exam_section.get("questions", {}).get("groups", [])
        sec_correct = 0
        sec_total = 0

        for gi, group in enumerate(groups):
            q_type = group.get("type", "unknown")
            answers = group.get("answers", [])
            items = group.get("items", [])
            answer_list = answers if answers else items

            for qi, correct_answer in enumerate(answer_list):
                key = f"q_{gi}_{qi}"
                user_ans = user_answers.get(key, "")
                correct_val = correct_answer if isinstance(correct_answer, str) else str(correct_answer)

                is_correct = user_ans.strip().lower() == correct_val.strip().lower()
                sec_correct += 1 if is_correct else 0
                sec_total += 1

                # Track per question type
                if q_type not in question_type_stats:
                    question_type_stats[q_type] = {"correct": 0, "total": 0}
                question_type_stats[q_type]["total"] += 1
                if is_correct:
                    question_type_stats[q_type]["correct"] += 1

        total_correct += sec_correct
        total_questions += sec_total
        section_results.append({
            "section": sec_num,
            "correct": sec_correct,
            "total": sec_total,
            "accuracy": round(sec_correct / sec_total * 100, 1) if sec_total > 0 else 0,
        })

    overall_band = _score_to_band(total_correct, total_questions)

    # Question type breakdown
    qt_breakdown = [
        {"type": qt, "correct": stats["correct"], "total": stats["total"],
         "accuracy": round(stats["correct"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0}
        for qt, stats in sorted(question_type_stats.items(), key=lambda x: -x[1]["total"])
    ]

    result = {
        "overall": {"correct": total_correct, "total": total_questions, "band": overall_band},
        "sections": section_results,
        "question_types": qt_breakdown,
        "time_taken_seconds": body.time_taken_seconds,
    }

    up.submitted_at = datetime.utcnow()
    up.user_answers = json.dumps({"sections": body.sections, "result": result})
    up.score = overall_band
    up.correct_count = total_correct
    up.total_questions = total_questions
    db.commit()

    return result
```

- [ ] **Step 3: Include router in main.py**

In `backend/app/main.py`, add:

```python
from app.routers.reading_exam import router as reading_exam_router
app.include_router(reading_exam_router, prefix="/api/generate", tags=["reading-exam"])
```

- [ ] **Step 4: Filter full tests by VIP in daily-reading**

In `backend/app/routers/reading.py`, modify `_available_for_user` to exclude `reading_full_test` for non-VIP users. Find where practices are queried and add:

```python
# After the base query, filter out full tests for non-VIP users:
# This goes in get_daily_reading endpoint, after getting available practices
# Filter: exclude reading_full_test content for non-VIP users
if current_user.role != 'vip':
    practices = [p for p in practices if '"reading_full_test"' not in (p.get('meta', {}).get('module', ''))]
```

- [ ] **Step 5: Run tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/reading_exam.py backend/app/routers/generate.py backend/app/routers/reading.py backend/app/main.py
git commit -m "feat: reading exam cron + submit endpoint + VIP filter"
```

---

## Chunk 3: Frontend — Full Reading Exam View

### Task 6: Add API method + types

**Files:**
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add ReadingExam types**

In `frontend/src/types/index.ts`, add:

```typescript
export interface ReadingExamSection {
  section_number: number;
  difficulty_profile: { text_complexity: number; inference_demand: number; question_difficulty: number };
  meta: { topic: string; word_count: number };
  passage: { title: string; content: string };
  questions: { groups: any[] };
  question_count: number;
}

export interface ReadingExamResult {
  overall: { correct: number; total: number; band: number };
  sections: { section: number; correct: number; total: number; accuracy: number }[];
  question_types: { type: string; correct: number; total: number; accuracy: number }[];
  time_taken_seconds: number;
}
```

- [ ] **Step 2: Add API method**

In `frontend/src/api/index.ts`, add to practiceAPI:

```typescript
submitReadingExam: (practiceId: number, sections: any[], timeTaken: number) =>
  api.post('/generate/submit-ai-reading-exam', {
    practice_id: practiceId,
    sections,
    time_taken_seconds: timeTaken,
  }),
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/api/index.ts
git commit -m "feat: reading exam API types and submit method"
```

---

### Task 7: Build AIReadingFullTestView

**Files:**
- Create: `frontend/src/components/practice/AIReadingFullTestView.tsx`

- [ ] **Step 1: Create the full test view component**

Build a component with:
- State machine: `intro → exam → confirm_submit → processing → results`
- Intro: shows 3 section topics, total questions, 60-min warning, "Start Exam" button
- Exam: section tabs [1] [2] [3], countdown timer, passage + questions, answer persistence
- Auto-submit at 60 min, warning at 55 min
- Results: overall band + per-section breakdown + question-type accuracy + explanations

The component should accept `exercise` (with `sections` array) and `onBack` props. Reuse the existing question rendering patterns from AIReadingView.tsx but in exam mode (no instant feedback).

Key behaviors:
- All answers stored in `answersRef.current[sectionIdx][groupIdx_questionIdx]`
- Free navigation between sections via tabs
- Timer counts down from 3600 seconds
- Submit sends all answers to `practiceAPI.submitReadingExam()`
- Results screen uses ConfettiBurst + CountUp animations

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/practice/AIReadingFullTestView.tsx
git commit -m "feat: AIReadingFullTestView — 3 passages, timer, exam mode"
```

---

### Task 8: Wire into Practice page

**Files:**
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Import and route to full test view**

Add import:
```tsx
import AIReadingFullTestView from '../components/practice/AIReadingFullTestView';
```

In the exercise view routing (where `currentAIExercise` is rendered), add a check:
```tsx
// If the selected reading exercise is a full test, use the full test view
if (currentAIExercise?.meta?.module === 'reading_full_test') {
  return <AIReadingFullTestView exercise={currentAIExercise} onBack={handleBack} />;
}
```

- [ ] **Step 2: Show full test cards in Exam tab for VIP users**

In the Exam mode section, for reading skill when user is VIP, filter reading exercises that are full tests:

```tsx
{activeSkill === 'reading' && isVip && (
  aiReadingExercises.filter(ex => ex.meta?.module === 'reading_full_test').length > 0 ? (
    aiReadingExercises.filter(ex => ex.meta?.module === 'reading_full_test').map((ex, i) => (
      <button key={i} className="exercise-item exercise-item-highlight"
        style={{ borderLeftColor: '#4F46E5' }}
        onClick={() => handleSelectAIExercise(ex)}>
        <span className="exercise-title">{ex.meta.topic}</span>
        <span className="exercise-meta">Full Test · 60 min · {ex.meta.total_questions || 30}q</span>
      </button>
    ))
  ) : (
    <p className="empty-list">No full tests available yet. Check back tomorrow.</p>
  )
)}
```

- [ ] **Step 3: TypeScript check + tests**

```bash
cd frontend && npx tsc -b --noEmit && npx vitest run
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Practice.tsx
git commit -m "feat: wire reading full test into Practice page with VIP gating"
```

---

## Chunk 4: Integration, Testing, Deploy

### Task 9: End-to-end test + deploy

- [ ] **Step 1: Run all backend tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Run all frontend tests**

```bash
cd frontend && npx vitest run
```

- [ ] **Step 3: Generate a test reading exam on VPS**

SSH into VPS and manually trigger one reading exam generation:

```bash
ssh root@VPS "cd /root/IELTS-Assist/backend && source venv/bin/activate && \
  DATABASE_URL=postgresql://ielts_user:ielts_pass_2024@localhost:5432/ielts_assist \
  python3 -c '
import sys, json, os; sys.path.insert(0, \".\")
os.environ[\"DATABASE_URL\"] = \"postgresql://ielts_user:ielts_pass_2024@localhost:5432/ielts_assist\"
from app.services.ai.reading_exam import generate_reading_exam
exam = generate_reading_exam()
if exam: print(f\"Generated exam: {exam[\"meta\"][\"topic\"]}, {exam[\"meta\"][\"total_questions\"]}q\")
else: print(\"Generation failed\")
'"
```

- [ ] **Step 4: Tag, release, deploy**

```bash
git tag v0.28.0
git push origin main v0.28.0
# Create GitHub release
# Deploy to VPS
```

- [ ] **Step 5: Seed a reading exam for test user**

After deploy, manually seed one reading exam into the pool and clear active reading cards for the test user so it gets dealt.

---

## Build Order Summary

1. User role field (Task 1) — 5 min
2. VIP Gate component (Task 2) — 10 min
3. Difficulty profile in generator (Task 3) — 15 min
4. Reading exam orchestrator (Task 4) — 15 min
5. Cron + submit endpoint + VIP filter (Task 5) — 20 min
6. API types (Task 6) — 5 min
7. AIReadingFullTestView (Task 7) — 30 min (largest task)
8. Wire into Practice page (Task 8) — 10 min
9. E2E test + deploy (Task 9) — 15 min
