import json
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.ai.practice_generator import practice_generator
from app.services.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ACTIVE_CARDS = 3
POOL_TARGET = 5


# ── helpers ───────────────────────────────────────────────────────────────────

def _active_cards(user_id: int, db: Session) -> list:
    return db.query(UserPractice).filter(
        UserPractice.user_id == user_id,
        UserPractice.submitted_at.is_(None)
    ).all()


def _available_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    """Global pool practices not yet dealt to this user."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id
    ).subquery()
    q = (
        db.query(GeneratedPractice)
        .filter(
            GeneratedPractice.skill == "reading",
            ~GeneratedPractice.id.in_(served),
        )
        .order_by(GeneratedPractice.generated_date.asc())
    )
    if exclude_topics:
        filtered = [t for t in exclude_topics if t]
        if filtered:
            q = q.filter(~GeneratedPractice.topic.in_(filtered))
    return q.limit(limit).all() if limit else q.all()


def _with_db_id(practice: GeneratedPractice) -> dict:
    content = json.loads(practice.content)
    content["practice_db_id"] = practice.id
    return content


def _replenish(user_id: int) -> None:
    """Background task: top up global pool so user has >= POOL_TARGET available."""
    db = SessionLocal()
    try:
        available_count = len(_available_for_user(user_id, db))
        needed = POOL_TARGET - available_count
        if needed <= 0:
            return
        logger.info(f"Replenishing pool: generating {needed} exercise(s) for user {user_id}")
        recent = (
            db.query(GeneratedPractice.topic)
            .filter(GeneratedPractice.skill == "reading", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(15)
            .all()
        )
        avoid_list = [r[0] for r in recent if r[0]]
        topic_hint = f"avoid: {', '.join(avoid_list)}" if avoid_list else ""
        for _ in range(needed):
            practice = practice_generator.generate_practice(topic_hint)
            if practice:
                db.add(GeneratedPractice(
                    skill="reading",
                    topic=practice.get("meta", {}).get("topic", ""),
                    content=json.dumps(practice),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
    except Exception as e:
        logger.error(f"Replenishment error: {e}")
    finally:
        db.close()


def daily_generate() -> None:
    """Cron job: unconditionally add 3 fresh exercises to global pool."""
    db = SessionLocal()
    try:
        logger.info("Daily generation: adding 3 new exercises")
        for _ in range(3):
            practice = practice_generator.generate_practice()
            if practice:
                db.add(GeneratedPractice(
                    skill="reading",
                    topic=practice.get("meta", {}).get("topic", ""),
                    content=json.dumps(practice),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
        logger.info("Daily generation complete")
    except Exception as e:
        logger.error(f"Daily generation error: {e}")
    finally:
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/daily-reading")
def get_daily_reading(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's active cards (up to 3). Deals from pool to fill slots."""
    active = _active_cards(current_user.id, db)
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
        new_gps = _available_for_user(current_user.id, db, limit=slots_needed, exclude_topics=active_topics)
        for gp in new_gps:
            db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
            practices.append(_with_db_id(gp))
        if new_gps:
            db.commit()

    background_tasks.add_task(_replenish, current_user.id)
    return {"practices": practices}


@router.post("/generate-more")
def generate_more(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pop 1 practice from pool instantly. Returns pool_empty if none available."""
    active_cards = _active_cards(current_user.id, db)
    if len(active_cards) >= MAX_ACTIVE_CARDS:
        return {"practices": [], "at_capacity": True}

    active_topics = [
        db.get(GeneratedPractice, up.practice_id).topic
        for up in active_cards
        if db.get(GeneratedPractice, up.practice_id) and db.get(GeneratedPractice, up.practice_id).topic
    ]
    available = _available_for_user(current_user.id, db, limit=1, exclude_topics=active_topics)
    if not available:
        background_tasks.add_task(_replenish, current_user.id)
        return {"practices": [], "pool_empty": True}

    gp = available[0]
    db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
    db.commit()

    background_tasks.add_task(_replenish, current_user.id)
    return {"practices": [_with_db_id(gp)]}


class SubmitAIReadingBody(BaseModel):
    practice_id: int
    user_answers: str  # JSON string — stored for future Mistakes area
    score: float
    correct_count: int
    total_questions: int


@router.post("/submit-ai-reading")
def submit_ai_reading(
    body: SubmitAIReadingBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an AI reading exercise as completed for this user."""
    up = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == body.practice_id,
        UserPractice.submitted_at.is_(None),
    ).first()
    if not up:
        raise HTTPException(status_code=404, detail="Active practice not found")

    up.submitted_at = datetime.utcnow()
    up.user_answers = body.user_answers
    up.score = body.score
    up.correct_count = body.correct_count
    up.total_questions = body.total_questions
    db.commit()

    background_tasks.add_task(_replenish, current_user.id)
    return {"ok": True}


@router.post("/trigger-replenish")
def trigger_replenish(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    """Fire-and-forget: start background pool replenishment."""
    background_tasks.add_task(_replenish, current_user.id)
    return {"ok": True}


@router.get("/pool-status")
def pool_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return pool stats for the current user."""
    active = len(_active_cards(current_user.id, db))
    available = len(_available_for_user(current_user.id, db))
    return {"active": active, "available": available}


# ── admin / seed ──────────────────────────────────────────────────────────────

@router.post("/generate-reading")
def generate_reading_practice(
    count: int = 3,
    topic_hint: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: force-generate N exercises into global pool."""
    generated = []
    for _ in range(count):
        practice = practice_generator.generate_practice(topic_hint)
        if practice:
            db.add(GeneratedPractice(
                skill="reading",
                topic=practice.get("meta", {}).get("topic", ""),
                content=json.dumps(practice),
                is_validated=True,
                generated_date=datetime.utcnow(),
            ))
            generated.append(practice)
    db.commit()
    return {"generated": len(generated), "practices": generated}
