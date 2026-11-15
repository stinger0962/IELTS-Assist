import json
import logging
import math
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, Topic, User, UserPractice
from app.services.ai.writing_config import generate_metadata as writing_generate_metadata
from app.services.ai.writing_grader import WritingGrader
from app.services.auth import get_current_user
from app.services.quota import quota
from app.services.study_pass import (
    finalize_writing_review, release_writing_review, reserve_writing_review,
)

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


def _legacy_writing_quota(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Flag-off preserves the old dependency timing. Enabled requests are metered
    # only once an actual provider attempt is about to start.
    if not settings.STUDY_PASS_ENABLED:
        quota("grade")(db, current_user)


def _validate_writing_review(result: dict, essay: str) -> None:
    """Reject incomplete/malformed provider output before a paid result is saved."""
    def invalid():
        raise HTTPException(status_code=502, detail={
            "code": "writing_review_invalid",
            "message": "AI feedback was incomplete. Your review allowance was restored. Please retry.",
        })

    def band(value):
        return (type(value) in (int, float) and math.isfinite(value)
                and 0 <= value <= 9)

    if not isinstance(result, dict):
        invalid()
    er = result.get("examiner_result")
    cf = result.get("coaching_feedback")
    if not isinstance(er, dict) or not band(er.get("overall_band")):
        invalid()
    for name in ("task_response", "coherence_cohesion", "lexical_resource",
                 "grammatical_range_accuracy"):
        criterion = er.get(name)
        if (not isinstance(criterion, dict) or not band(criterion.get("band"))
                or not isinstance(criterion.get("evidence"), str)):
            invalid()
        flags = criterion.get("task_completion")
        if flags is not None and (not isinstance(flags, dict)
                or not all(isinstance(k, str) and isinstance(v, bool) for k, v in flags.items())):
            invalid()
    if not isinstance(cf, dict) or not isinstance(cf.get("summary"), str):
        invalid()
    for field in ("strengths", "improvements"):
        values = cf.get(field)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            invalid()
    annotations = result.get("annotations")
    if not isinstance(annotations, list):
        invalid()
    for ann in annotations:
        if (not isinstance(ann, dict)
                or not all(isinstance(ann.get(k), str) for k in
                           ("category", "severity", "suggestion"))
                or type(ann.get("start_char")) is not int
                or type(ann.get("end_char")) is not int
                or not 0 <= ann["start_char"] < ann["end_char"] <= len(essay)):
            invalid()


@router.post("/submit-ai-writing", dependencies=[Depends(_legacy_writing_quota)])
def submit_ai_writing(
    body: SubmitAIWritingBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grade a writing exercise; enabled pass reservations cover successful work only."""
    query = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == body.practice_id,
    )
    # Preserve the existing active-card-only behavior unless monetization is enabled.
    if not settings.STUDY_PASS_ENABLED:
        query = query.filter(UserPractice.submitted_at.is_(None))
    up = query.first()
    if not up:
        raise HTTPException(status_code=404, detail="Active practice not found")

    essay = body.essay.strip()
    if len(essay) < 50:
        raise HTTPException(status_code=400, detail="Essay is too short to grade")

    if up.submitted_at is not None:
        # Retrying a lost successful response must never run or debit a second review.
        # Match grading inputs, not elapsed time: the timer keeps running after network errors.
        saved = json.loads(up.user_answers or "{}")
        if (saved.get("essay") != essay
                or saved.get("submission_mode") != body.submission_mode
                or not isinstance(saved.get("grading"), dict)):
            raise HTTPException(status_code=409, detail={
                "code": "writing_already_submitted",
                "message": "This exercise already has a different submitted answer.",
            })
        return {
            "ok": True, "grading": saved["grading"],
            "word_count": saved["word_count"], "overall_band": up.score,
        }

    gp = db.get(GeneratedPractice, body.practice_id)
    if not gp or (settings.STUDY_PASS_ENABLED and gp.skill != "writing"):
        raise HTTPException(status_code=404, detail="Practice not found")
    practice_content = json.loads(gp.content)
    prompt_data = practice_content.get("prompt_metadata", practice_content.get("prompt", {}))

    # This durable reservation blocks duplicate in-flight calls. The service commits
    # it before expensive work; finalization below shares the result transaction.
    reservation = reserve_writing_review(db, current_user, body.practice_id)
    try:
        if settings.STUDY_PASS_ENABLED:
            quota("grade")(db, current_user)
        grading_result = WritingGrader().grade(essay, prompt_data)
        if settings.STUDY_PASS_ENABLED:
            _validate_writing_review(grading_result, essay)
        word_count = len(essay.split())
        overall_band = grading_result.get("examiner_result", {}).get("overall_band", 0)
        up.submitted_at = datetime.utcnow()
        up.user_answers = json.dumps({
            "essay": essay, "word_count": word_count,
            "time_seconds": body.time_seconds,
            "submission_mode": body.submission_mode, "grading": grading_result,
        })
        up.score = overall_band
        up.correct_count = 0
        up.total_questions = 4
        finalize_writing_review(db, reservation)
        db.commit()
    except Exception:
        # Roll back any result write before releasing the matching pending token.
        # Release is idempotent and cannot refund a successfully finalized review.
        db.rollback()
        release_writing_review(db, reservation)
        raise

    _extract_writing_topics(grading_result, current_user.id, db)
    background_tasks.add_task(_replenish_writing, current_user.id)
    return {
        "ok": True, "grading": grading_result,
        "word_count": word_count, "overall_band": overall_band,
    }
