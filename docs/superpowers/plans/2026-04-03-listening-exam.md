# Full Listening Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full IELTS Listening exam simulation with 4 sequential audio sections, 40 questions, progressive difficulty, and VIP-gated access.

**Architecture:** Orchestrator layer (`listening_exam.py`) calls the existing `ListeningGenerator` 4 times with different format hints and difficulty profiles. Each section gets its own TTS audio. Submit endpoint scores all 4 sections. Frontend uses sequential audio playback with prep/play phases. Reuses VIP gate, recent exams, and review patterns from reading exam.

**Tech Stack:** FastAPI, SQLAlchemy, OpenAI GPT-4o-mini, Google Cloud TTS, React/TypeScript

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/services/ai/listening_exam.py` | Create | Orchestrator: section profiles, `generate_listening_exam()`, validator |
| `backend/app/routers/listening_exam.py` | Create | `POST /submit-ai-listening-exam` endpoint |
| `backend/app/routers/generate.py` | Modify | Daily cron: add 1 listening exam generation |
| `backend/app/routers/listening.py` | Modify | Filter `listening_full_test` from daily-listening for non-VIP |
| `backend/app/main.py` | Modify | Include listening_exam router |
| `frontend/src/api/index.ts` | Modify | Add `submitListeningExam()` API method |
| `frontend/src/components/practice/AIListeningFullTestView.tsx` | Create | Full test UI: sequential audio, prep/play phases, results |
| `frontend/src/pages/Practice.tsx` | Modify | Exam tab for listening: show full test cards, recent exams |

---

### Task 1: Listening Exam Orchestrator

**Files:**
- Create: `backend/app/services/ai/listening_exam.py`

- [ ] **Step 1: Create listening_exam.py with section profiles and orchestrator**

```python
"""Listening Exam Orchestrator.

Generates a full IELTS-style listening exam: 4 sections with progressive difficulty.
Calls the existing ListeningGenerator 4 times with different format hints.
"""
import json
import logging

from app.services.ai.listening_generator import ListeningGenerator

logger = logging.getLogger(__name__)

SECTION_PROFILES = [
    {
        "section_number": 1,
        "format_hint": "conversation",
        "category_hint": "daily_life",
        "description": "Two speakers in a daily/social context",
    },
    {
        "section_number": 2,
        "format_hint": "monologue",
        "category_hint": "public_info",
        "description": "Monologue on a social/everyday topic",
    },
    {
        "section_number": 3,
        "format_hint": "discussion",
        "category_hint": "academic",
        "description": "Discussion in an educational/training context",
    },
    {
        "section_number": 4,
        "format_hint": "lecture",
        "category_hint": "academic",
        "description": "Academic lecture or monologue",
    },
]


def generate_listening_exam(avoid_topics: list[str] | None = None) -> dict | None:
    """Generate a full listening exam with 4 sections.
    
    Returns the complete exam content dict, or None if generation fails.
    """
    generator = ListeningGenerator()
    used_topics = list(avoid_topics or [])
    sections = []

    for profile in SECTION_PROFILES:
        section = _generate_section(generator, profile, used_topics)
        if not section:
            logger.error(f"[ListeningExam] Failed to generate section {profile['section_number']}")
            return None
        sections.append(section)
        topic = section.get("meta", {}).get("topic", "")
        if topic:
            used_topics.append(topic)

    if not _validate_exam(sections):
        logger.error("[ListeningExam] Validation failed")
        return None

    topics_str = ", ".join(s["meta"]["topic"] for s in sections)
    total_q = sum(s["question_count"] for s in sections)

    return {
        "meta": {
            "module": "listening_full_test",
            "topic": f"Full Listening Test — {topics_str}",
            "total_questions": total_q,
            "time_limit_minutes": 30,
            "version": "v1",
        },
        "sections": sections,
    }


def _generate_section(generator: ListeningGenerator, profile: dict, avoid_topics: list[str]) -> dict | None:
    """Generate one exam section using the existing listening generator."""
    topic_hint = "avoid:" + ",".join(avoid_topics) if avoid_topics else ""

    for attempt in range(3):
        practice = generator.generate(
            topic_hint=topic_hint,
            format_hint=profile["format_hint"],
        )
        if not practice:
            continue

        # Count questions
        questions = practice.get("questions", {})
        if isinstance(questions, list):
            q_count = len(questions)
        else:
            groups = questions.get("groups", [])
            q_count = sum(len(g.get("items", [])) for g in groups)

        return {
            "section_number": profile["section_number"],
            "format": profile["format_hint"],
            "description": profile["description"],
            "meta": practice.get("meta", {}),
            "audio_url": practice.get("meta", {}).get("audio_url", ""),
            "transcript": practice.get("transcript", ""),
            "questions": practice.get("questions", {}),
            "question_count": q_count,
        }

    return None


def _validate_exam(sections: list[dict]) -> bool:
    """Lightweight validation for assembled exam."""
    if len(sections) != 4:
        return False
    for s in sections:
        if s.get("question_count", 0) < 5:
            logger.warning(f"[ListeningExam] Section {s['section_number']} has only {s.get('question_count')} questions")
            return False
        if not s.get("audio_url"):
            logger.warning(f"[ListeningExam] Section {s['section_number']} missing audio")
            return False
    topics = [s["meta"].get("topic", "") for s in sections]
    if len(set(topics)) < 4:
        logger.warning(f"[ListeningExam] Duplicate topics: {topics}")
        return False
    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/ai/listening_exam.py
git commit -m "feat: listening exam orchestrator — 4-section generator"
```

---

### Task 2: Listening Exam Submit Endpoint

**Files:**
- Create: `backend/app/routers/listening_exam.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create listening_exam.py router**

Follow the exact pattern from `backend/app/routers/reading_exam.py`. The submit endpoint scores all 4 sections, maps raw score to band using a 40-question band map.

```python
"""Listening exam endpoints — submit + scoring."""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.auth import get_current_user
from app.utils.completion_match import completion_match

router = APIRouter()
logger = logging.getLogger(__name__)

BAND_MAP_40 = [
    (37, 8.5), (32, 7.5), (27, 7.0), (23, 6.5),
    (18, 6.0), (14, 5.5), (10, 5.0), (0, 4.0),
]


def _score_to_band(correct: int) -> float:
    for threshold, band in BAND_MAP_40:
        if correct >= threshold:
            return band
    return 4.0


class ListeningExamSubmission(BaseModel):
    practice_id: int
    sections: list[dict]
    time_taken_seconds: int


@router.post("/submit-ai-listening-exam")
def submit_listening_exam(
    body: ListeningExamSubmission,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Score a full listening exam submission."""
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

    section_results = []
    total_correct = 0
    total_questions = 0
    question_type_stats = {}

    for exam_section in exam_sections:
        sec_num = exam_section["section_number"]
        user_section = next((s for s in body.sections if s.get("section_number") == sec_num), None)
        user_answers = user_section.get("answers", {}) if user_section else {}

        questions = exam_section.get("questions", {})
        groups = questions.get("groups", []) if isinstance(questions, dict) else []
        sec_correct = 0
        sec_total = 0

        for gi, group in enumerate(groups):
            q_type = group.get("type", "unknown")
            items = group.get("items", [])
            if q_type not in question_type_stats:
                question_type_stats[q_type] = {"correct": 0, "total": 0}

            for qi, item in enumerate(items):
                key = f"q_{gi}_{qi}"
                user_ans = user_answers.get(key, "").strip()
                correct_val = str(item.get("answer", "")).strip()

                if q_type in ("completion", "form_completion", "note_completion", "sentence_completion", "summary_completion", "short_answer"):
                    is_correct = completion_match(user_ans, correct_val)
                elif q_type == "matching":
                    is_correct = user_ans.upper() == correct_val.upper()
                else:
                    is_correct = user_ans.upper() == correct_val.upper()

                sec_correct += 1 if is_correct else 0
                sec_total += 1
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

    overall_band = _score_to_band(total_correct)

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

Note: `completion_match` import — check if it exists as a backend util. If not, inline a simple match: `user_ans.lower() == correct_val.lower()`. The frontend `completionMatch` is TypeScript-only. For the backend, use the same scoring logic as reading_exam.py (direct string comparison) since we don't have a Python completion_match util yet.

- [ ] **Step 2: Include router in main.py**

Add to `backend/app/main.py`:
```python
from app.routers import listening_exam
app.include_router(listening_exam.router, prefix="/api/generate", tags=["generate"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/listening_exam.py backend/app/main.py
git commit -m "feat: listening exam submit endpoint with 40-question band mapping"
```

---

### Task 3: Cron + VIP Filter

**Files:**
- Modify: `backend/app/routers/generate.py` (daily cron)
- Modify: `backend/app/routers/listening.py` (VIP filter)

- [ ] **Step 1: Add listening exam to daily cron**

In `generate.py`, inside `daily_generate()`, after the reading exam generation block, add:

```python
# Generate 1 full listening exam
try:
    from app.services.ai.listening_exam import generate_listening_exam
    logger.info("Daily generation: generating 1 full listening exam")
    exam = generate_listening_exam()
    if exam:
        db.add(GeneratedPractice(
            skill="listening",
            topic=exam["meta"]["topic"],
            content=json.dumps(exam),
            is_validated=True,
            generated_date=datetime.utcnow(),
        ))
        db.commit()
        logger.info("Daily listening exam generation complete")
    else:
        logger.warning("Daily listening exam generation failed")
except Exception as e:
    logger.error(f"Daily listening exam error: {e}")
```

- [ ] **Step 2: Filter full tests from daily-listening for non-VIP**

In `listening.py`, in `get_daily_listening()`, add the same VIP filter as reading.py:

```python
# Filter out full tests for non-VIP users
if current_user.role != 'vip':
    available = [p for p in available if 'listening_full_test' not in (json.loads(p.content).get('meta', {}).get('module', ''))]
```

Or use the simpler approach: filter when dealing cards by checking `topic.startswith('Full Listening Test')`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/generate.py backend/app/routers/listening.py
git commit -m "feat: daily cron generates 1 listening exam + VIP filter"
```

---

### Task 4: Frontend API + Types

**Files:**
- Modify: `frontend/src/api/index.ts`

- [ ] **Step 1: Add submitListeningExam API method**

```typescript
submitListeningExam: (practiceId: number, sections: any[], timeTaken: number) =>
    api.post('/generate/submit-ai-listening-exam', {
      practice_id: practiceId,
      sections,
      time_taken_seconds: timeTaken,
    }),
```

Add this next to the existing `submitReadingExam` method.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/index.ts
git commit -m "feat: add submitListeningExam API method"
```

---

### Task 5: AIListeningFullTestView Component

**Files:**
- Create: `frontend/src/components/practice/AIListeningFullTestView.tsx`

This is the largest task. Follow `AIReadingFullTestView.tsx` as the template but with these key differences:

1. **Sequential audio playback** instead of free navigation between sections
2. **Prep phase** (30s) before each section's audio plays
3. **Audio player** for each section
4. **Transcript tab** (instead of Passage tab) in review mode

- [ ] **Step 1: Create the component**

The component should implement:
- Stage machine: `intro → section_N_prep → section_N_play → ... → review → confirm → processing → results`
- Current section index tracked in state
- Audio ref for current section's audio
- 30s prep countdown before audio auto-plays
- Questions visible during audio playback
- After audio ends: 30s to finalize answers, auto-advance to next section
- After section 4: review screen showing all answers
- Submit: calls `practiceAPI.submitListeningExam()`
- Results: same clickable section cards + review mode as reading exam
- Review mode: Transcript tab + Questions tab (reuse pattern from reading exam)

Key state:
```typescript
const [stage, setStage] = useState<Stage>(isReviewMode ? 'results' : 'intro');
const [currentSection, setCurrentSection] = useState(0);
const [prepTimer, setPrepTimer] = useState(30);
const [audioEnded, setAudioEnded] = useState(false);
const [postAudioTimer, setPostAudioTimer] = useState(30);
const answersRef = useRef<Record<number, Record<string, string>>>({});
const audioRef = useRef<HTMLAudioElement | null>(null);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/practice/AIListeningFullTestView.tsx
git commit -m "feat: AIListeningFullTestView — sequential audio exam UI"
```

---

### Task 6: Wire into Practice.tsx

**Files:**
- Modify: `frontend/src/pages/Practice.tsx`

- [ ] **Step 1: Import and render AIListeningFullTestView**

Add import:
```typescript
import AIListeningFullTestView from '../components/practice/AIListeningFullTestView';
```

In the listening exercise view section, add a check for `listening_full_test` module (same pattern as reading full test):
```typescript
if (currentAIListening?.meta?.module === 'listening_full_test') {
  return (
    <div className="practice">
      <AIListeningFullTestView exercise={currentAIListening} onBack={handleBack} />
      <style>{sharedExerciseStyles}</style>
    </div>
  );
}
```

In the Exam tab section, add listening exam cards (same pattern as reading):
```typescript
) : activeSkill === 'listening' ? (
  // Show listening full test cards for VIP
  aiListeningExercises.filter(ex => ex.meta?.module === 'listening_full_test').length > 0 ? (
    aiListeningExercises.filter(ex => ex.meta?.module === 'listening_full_test').map((ex, i) => {
      const topics = ((ex.meta as any).topic || '').replace('Full Listening Test — ', '').split(', ');
      const totalQ = (ex.meta as any).total_questions || 40;
      return (
        <div key={i} className="exam-card" onClick={() => handleSelectAIListening(ex)}>
          <div className="exam-card-header">
            <span className="exam-card-icon">🎧</span>
            <div>
              <h3 className="exam-card-title">Full Listening Test</h3>
              <span className="exam-card-meta">30 min · {totalQ} questions · 4 sections</span>
            </div>
          </div>
          <div className="exam-card-topics">
            {topics.map((t: string, ti: number) => (
              <span key={ti} className="exam-topic-pill">S{ti + 1}: {t.trim()}</span>
            ))}
          </div>
          <div className="exam-card-cta">Start Exam →</div>
        </div>
      );
    })
  ) : (
    <p className="empty-list">No full tests available yet. Check back tomorrow.</p>
  )
```

Also add recent exams for listening (reuse same pattern as reading):
```typescript
{activeSkill === 'listening' && isVip && recentExams.length > 0 && (
  // ... same recent exam cards as reading
)}
```

Note: The `loadRecentExams` function already accepts a skill param. Update it to load for the active skill:
```typescript
const loadRecentExams = async () => {
  try {
    const res = await practiceAPI.getRecentExams(activeSkill);
    setRecentExams(Array.isArray(res.data) ? res.data : []);
  } catch { setRecentExams([]); }
};
```

Also filter `listening_full_test` from the practice tab's listening list (same as reading).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Practice.tsx
git commit -m "feat: wire listening exam into Practice page — exam tab + review"
```

---

### Task 7: Test, Tag, Deploy

- [ ] **Step 1: Run backend tests**

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Fix any TS errors.

- [ ] **Step 3: Commit, tag, push**

```bash
git tag v0.29.0
git push origin main v0.29.0
```

- [ ] **Step 4: Deploy to VPS**

```bash
ssh root@152.42.251.169 "cd /root/IELTS-Assist && git pull && cd frontend && npm run build && cp -r dist/* /var/www/ielts-assist/ && cd ../backend && source venv/bin/activate && pip install -r requirements.txt -q && systemctl restart ielts-backend"
```

- [ ] **Step 5: Seed a listening exam**

```bash
# On VPS — run the generator to seed 1 exam
ssh root@152.42.251.169 "cd /root/IELTS-Assist/backend && source venv/bin/activate && DATABASE_URL=... OPENAI_API_KEY=... python3 -c '...generate_listening_exam()...'"
```

- [ ] **Step 6: Create GitHub release**
