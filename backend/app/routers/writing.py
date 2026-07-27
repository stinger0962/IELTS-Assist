import json
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, Topic, User, UserPractice
from app.services.ai.writing_config import generate_metadata as writing_generate_metadata
from app.services.ai.writing_grader import WritingGrader
from app.services.auth import get_current_user
from app.services.quota import quota

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ACTIVE_CARDS = 3
POOL_TARGET = 5


def _with_db_id(practice: GeneratedPractice) -> dict:
    content = json.loads(practice.content)
    content["practice_db_id"] = practice.id
    return content


# ── writing pool helpers ─────────────────────────────────────────────────────

def _available_writing_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    """Global writing pool practices not yet dealt to this user."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id
    ).subquery()
    q = (
        db.query(GeneratedPractice)
        .filter(
            GeneratedPractice.skill == "writing",
            ~GeneratedPractice.id.in_(served),
        )
        .order_by(GeneratedPractice.generated_date.asc())
    )
    if exclude_topics:
        filtered = [t for t in exclude_topics if t]
        if filtered:
            q = q.filter(~GeneratedPractice.topic.in_(filtered))
    return q.limit(limit).all() if limit else q.all()


def _active_writing_cards(user_id: int, db: Session) -> list:
    """Active (unsubmitted) writing cards for this user."""
    return (
        db.query(UserPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at.is_(None),
            GeneratedPractice.skill == "writing",
        )
        .all()
    )


def _replenish_writing(user_id: int) -> None:
    """Background task: top up writing pool. Instant — no GPT call needed."""
    db = SessionLocal()
    try:
        available_count = len(_available_writing_for_user(user_id, db))
        needed = POOL_TARGET - available_count
        if needed <= 0:
            return
        logger.info(f"Replenishing writing pool: adding {needed} prompt(s) for user {user_id}")
        recent = (
            db.query(GeneratedPractice)
            .filter(GeneratedPractice.skill == "writing", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(30)
            .all()
        )
        avoid_topics = [r.topic for r in recent if r.topic]
        # Also extract domains and essay types from recent content
        avoid_domains = []
        avoid_types = []
        for r in recent[:10]:
            try:
                c = json.loads(r.content)
                meta = c.get("meta", {})
                if meta.get("domain"):
                    avoid_domains.append(meta["domain"])
                if meta.get("essay_type"):
                    avoid_types.append(meta["essay_type"])
            except Exception:
                pass
        for _ in range(needed):
            prompt_data = writing_generate_metadata(
                avoid_topics=avoid_topics,
                avoid_domains=avoid_domains,
                avoid_types=avoid_types,
            )
            if prompt_data:
                content = {
                    "meta": {
                        "module": "writing_task2",
                        "essay_type": prompt_data["essay_type"],
                        "domain": prompt_data["domain"],
                        "topic": prompt_data.get("topic_title", prompt_data["statement"][:60]),
                        "word_limit": {"min": 250, "recommended": 280},
                    },
                    "prompt": {
                        "statement": prompt_data["statement"],
                        "instruction": prompt_data["instruction"],
                        "notes": "Write at least 250 words. You should spend about 40 minutes on this task.",
                    },
                    "prompt_metadata": prompt_data,
                }
                db.add(GeneratedPractice(
                    skill="writing",
                    topic=prompt_data.get("topic_title", prompt_data["statement"][:60]),
                    content=json.dumps(content),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
    except Exception as e:
        logger.error(f"Writing replenishment error: {e}")
    finally:
        db.close()


def _extract_writing_topics(grading_result: dict, user_id: int, db: Session) -> None:
    """Create Topic flashcards from recurring annotation patterns.

    Only extracts teachable patterns that appear 2+ times in grammar/vocabulary
    categories. One-off typos and style suggestions are ignored.
    """
    try:
        annotations = grading_result.get("annotations", [])
        if len(annotations) < 2:
            return

        # Count by category — only grammar and vocabulary are teachable
        category_items: dict[str, list] = {}
        for ann in annotations:
            cat = ann.get("category", "")
            if cat in ("grammar", "vocabulary"):
                category_items.setdefault(cat, []).append(ann)

        for cat, items in category_items.items():
            if len(items) < 2:
                continue
            # Create one Topic per recurring category
            examples = "; ".join(
                f'"{it.get("original_text", "")}" → {it.get("suggestion", "")}'
                for it in items[:3]
            )
            title = f"Writing: {cat.title()} pattern"
            content = f"Recurring {cat} issue found in your essay. Examples: {examples}"
            db.add(Topic(
                user_id=user_id,
                skill="writing",
                category=cat,
                title=title,
                content=content,
                difficulty=3,
            ))
        db.commit()
    except Exception as e:
        logger.error(f"Writing topics extraction error: {e}")


def _seed_writing_pool(db: Session, count: int = 5) -> None:
    """Seed writing pool with prompts from hardcoded bank. No GPT call needed."""
    recent = (
        db.query(GeneratedPractice)
        .filter(GeneratedPractice.skill == "writing", GeneratedPractice.topic.isnot(None))
        .order_by(GeneratedPractice.generated_date.desc())
        .limit(30)
        .all()
    )
    avoid_topics = [r.topic for r in recent if r.topic]
    for _ in range(count):
        prompt_data = writing_generate_metadata(avoid_topics=avoid_topics)
        if prompt_data:
            content = {
                "meta": {
                    "module": "writing_task2",
                    "essay_type": prompt_data["essay_type"],
                    "domain": prompt_data["domain"],
                    "topic": prompt_data.get("topic_title", prompt_data["statement"][:60]),
                    "word_limit": {"min": 250, "recommended": 280},
                },
                "prompt": {
                    "statement": prompt_data["statement"],
                    "instruction": prompt_data["instruction"],
                    "notes": "Write at least 250 words. You should spend about 40 minutes on this task.",
                },
                "prompt_metadata": prompt_data,
            }
            db.add(GeneratedPractice(
                skill="writing",
                topic=prompt_data.get("topic_title", prompt_data["statement"][:60]),
                content=json.dumps(content),
                is_validated=True,
                generated_date=datetime.utcnow(),
            ))
    db.commit()


# ── writing endpoints ────────────────────────────────────────────────────────

@router.get("/daily-writing")
def get_daily_writing(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's active writing cards (up to 3). Deals from pool to fill slots."""
    active = _active_writing_cards(current_user.id, db)
    practices = [_with_db_id(db.get(GeneratedPractice, up.practice_id))
                 for up in active
                 if db.get(GeneratedPractice, up.practice_id)]

    slots_needed = MAX_ACTIVE_CARDS - len(practices)
    if slots_needed > 0:
        active_topics = [
            db.get(GeneratedPractice, up.practice_id).topic
            for up in active
            if db.get(GeneratedPractice, up.practice_id) and db.get(GeneratedPractice, up.practice_id).topic
        ]
        new_gps = _available_writing_for_user(current_user.id, db, limit=slots_needed, exclude_topics=active_topics)
        # If pool is empty, generate prompts on the fly (instant, no GPT)
        if not new_gps:
            _seed_writing_pool(db, count=slots_needed)
            new_gps = _available_writing_for_user(current_user.id, db, limit=slots_needed, exclude_topics=active_topics)
        for gp in new_gps:
            db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
            practices.append(_with_db_id(gp))
        if new_gps:
            db.commit()

    background_tasks.add_task(_replenish_writing, current_user.id)
    return {"practices": practices}


@router.post("/generate-more-writing")
def generate_more_writing(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pop 1 writing practice from pool instantly."""
    active_cards = _active_writing_cards(current_user.id, db)
    if len(active_cards) >= MAX_ACTIVE_CARDS:
        return {"practices": [], "at_capacity": True}

    active_topics = [
        db.get(GeneratedPractice, up.practice_id).topic
        for up in active_cards
        if db.get(GeneratedPractice, up.practice_id) and db.get(GeneratedPractice, up.practice_id).topic
    ]
    available = _available_writing_for_user(current_user.id, db, limit=1, exclude_topics=active_topics)
    if not available:
        _seed_writing_pool(db, count=3)
        available = _available_writing_for_user(current_user.id, db, limit=1, exclude_topics=active_topics)
    if not available:
        return {"practices": [], "pool_empty": True}

    gp = available[0]
    db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
    db.commit()

    background_tasks.add_task(_replenish_writing, current_user.id)
    return {"practices": [_with_db_id(gp)]}


class SubmitAIWritingBody(BaseModel):
    practice_id: int
    essay: str
    time_seconds: int
    submission_mode: str = "study"  # "study" or "exam"


@router.post("/submit-ai-writing", dependencies=[Depends(quota("grade"))])
def submit_ai_writing(
    body: SubmitAIWritingBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grade and submit an AI writing exercise. Sync GPT-4o grading (5-15s)."""
    # 1. Find active card
    up = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == body.practice_id,
        UserPractice.submitted_at.is_(None),
    ).first()
    if not up:
        raise HTTPException(status_code=404, detail="Active practice not found")

    # 2. Validate essay
    essay = body.essay.strip()
    if len(essay) < 50:
        raise HTTPException(status_code=400, detail="Essay is too short to grade")

    # 3. Load prompt data
    gp = db.get(GeneratedPractice, body.practice_id)
    if not gp:
        raise HTTPException(status_code=404, detail="Practice not found")
    practice_content = json.loads(gp.content)
    prompt_data = practice_content.get("prompt_metadata", practice_content.get("prompt", {}))

    # 4. Grade via GPT-4o (sync — takes 5-15s)
    grader = WritingGrader()
    grading_result = grader.grade(essay, prompt_data)

    # 5. Store results
    word_count = len(essay.split())
    overall_band = grading_result.get("examiner_result", {}).get("overall_band", 0)
    user_answers = json.dumps({
        "essay": essay,
        "word_count": word_count,
        "time_seconds": body.time_seconds,
        "submission_mode": body.submission_mode,
        "grading": grading_result,
    })

    up.submitted_at = datetime.utcnow()
    up.user_answers = user_answers
    up.score = overall_band
    up.correct_count = 0  # not applicable for writing
    up.total_questions = 4  # 4 criteria
    db.commit()

    # 6. Selective Topics extraction from recurring annotation patterns
    _extract_writing_topics(grading_result, current_user.id, db)

    # 7. Background replenish
    background_tasks.add_task(_replenish_writing, current_user.id)

    return {
        "ok": True,
        "grading": grading_result,
        "word_count": word_count,
        "overall_band": overall_band,
    }
