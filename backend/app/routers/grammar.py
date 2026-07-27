"""Grammar skill — pool helpers + endpoints."""
import json
import logging
import random
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.ai.grammar_generator import grammar_generator
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


# ── helpers ───────────────────────────────────────────────────────────────────

def _available_grammar_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    """Global grammar pool practices not yet dealt to this user."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id
    ).subquery()
    q = (
        db.query(GeneratedPractice)
        .filter(
            GeneratedPractice.skill == "grammar",
            ~GeneratedPractice.id.in_(served),
        )
        .order_by(GeneratedPractice.generated_date.asc())
    )
    if exclude_topics:
        filtered = [t for t in exclude_topics if t]
        if filtered:
            q = q.filter(~GeneratedPractice.topic.in_(filtered))
    return q.limit(limit).all() if limit else q.all()


def _active_grammar_cards(user_id: int, db: Session) -> list:
    """Active (unsubmitted) grammar cards for this user."""
    return (
        db.query(UserPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at.is_(None),
            GeneratedPractice.skill == "grammar",
        )
        .all()
    )


def _replenish_grammar(user_id: int) -> None:
    """Background task: top up grammar pool so user has >= POOL_TARGET available."""
    db = SessionLocal()
    try:
        available_count = len(_available_grammar_for_user(user_id, db))
        needed = POOL_TARGET - available_count
        if needed <= 0:
            return
        logger.info(f"Replenishing grammar pool: generating {needed} exercise(s) for user {user_id}")
        recent = (
            db.query(GeneratedPractice.topic)
            .filter(GeneratedPractice.skill == "grammar", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(60)
            .all()
        )
        avoid_list = [r[0] for r in recent if r[0]]
        bands = ["band_5_6", "band_6_7", "band_7_8"]
        random.shuffle(bands)
        for i in range(needed):
            practice = grammar_generator.generate(
                avoid_topics=avoid_list,
                prefer_band=bands[i % len(bands)],
            )
            if practice:
                db.add(GeneratedPractice(
                    skill="grammar",
                    topic=practice.get("meta", {}).get("grammar_topic", ""),
                    content=json.dumps(practice),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
    except Exception as e:
        logger.error(f"Grammar replenishment error: {e}")
    finally:
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/daily-grammar")
def get_daily_grammar(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's active grammar cards (up to 3). Deals from pool to fill slots."""
    active = _active_grammar_cards(current_user.id, db)
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
        new_gps = _available_grammar_for_user(current_user.id, db, limit=slots_needed, exclude_topics=active_topics)
        for gp in new_gps:
            db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
            practices.append(_with_db_id(gp))
        if new_gps:
            db.commit()

    background_tasks.add_task(_replenish_grammar, current_user.id)
    return {"practices": practices}


@router.post("/generate-more-grammar", dependencies=[Depends(quota("generate"))])
def generate_more_grammar(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pop 1 grammar practice from pool instantly."""
    active_cards = _active_grammar_cards(current_user.id, db)
    if len(active_cards) >= MAX_ACTIVE_CARDS:
        return {"practices": [], "at_capacity": True}

    active_topics = [
        db.get(GeneratedPractice, up.practice_id).topic
        for up in active_cards
        if db.get(GeneratedPractice, up.practice_id) and db.get(GeneratedPractice, up.practice_id).topic
    ]
    available = _available_grammar_for_user(current_user.id, db, limit=1, exclude_topics=active_topics)
    if not available:
        background_tasks.add_task(_replenish_grammar, current_user.id)
        return {"practices": [], "pool_empty": True}

    gp = available[0]
    db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
    db.commit()

    background_tasks.add_task(_replenish_grammar, current_user.id)
    return {"practices": [_with_db_id(gp)]}


class SubmitAIGrammarBody(BaseModel):
    practice_id: int
    user_answers: str
    score: float
    correct_count: int
    total_questions: int


@router.post("/submit-ai-grammar")
def submit_ai_grammar(
    body: SubmitAIGrammarBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an AI grammar exercise as completed for this user."""
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

    background_tasks.add_task(_replenish_grammar, current_user.id)
    return {"ok": True}


@router.post("/generate-grammar", dependencies=[Depends(quota("generate"))])
def generate_grammar_practice(
    count: int = 2,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: force-generate N grammar exercises into global pool."""
    generated = []
    for _ in range(count):
        practice = grammar_generator.generate()
        if practice:
            db.add(GeneratedPractice(
                skill="grammar",
                topic=practice.get("meta", {}).get("grammar_topic", ""),
                content=json.dumps(practice),
                is_validated=True,
                generated_date=datetime.utcnow(),
            ))
            generated.append(practice)
    db.commit()
    return {"generated": len(generated), "practices": generated}
