"""Listening skill — pool helpers + endpoints."""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.ai.listening_generator import listening_generator
from app.services.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ACTIVE_CARDS = 3
POOL_TARGET = 5


def _with_db_id(practice: GeneratedPractice) -> dict:
    content = json.loads(practice.content)
    content["practice_db_id"] = practice.id
    return content


# ── helpers ───────────────────────────────────────────────────────────────────

def _available_listening_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    """Global listening pool practices not yet dealt to this user (excludes full tests)."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id
    ).subquery()
    q = (
        db.query(GeneratedPractice)
        .filter(
            GeneratedPractice.skill == "listening",
            ~GeneratedPractice.id.in_(served),
            ~GeneratedPractice.content.contains('"listening_full_test"'),
        )
        .order_by(GeneratedPractice.generated_date.asc())
    )
    if exclude_topics:
        filtered = [t for t in exclude_topics if t]
        if filtered:
            q = q.filter(~GeneratedPractice.topic.in_(filtered))
    return q.limit(limit).all() if limit else q.all()


def _active_listening_cards(user_id: int, db: Session) -> list:
    """Active (unsubmitted) listening cards for this user (excludes full tests)."""
    return (
        db.query(UserPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at.is_(None),
            GeneratedPractice.skill == "listening",
            ~GeneratedPractice.content.contains('"listening_full_test"'),
        )
        .all()
    )


def _replenish_listening(user_id: int) -> None:
    """Background task: top up listening pool so user has >= POOL_TARGET available."""
    db = SessionLocal()
    try:
        available_count = len(_available_listening_for_user(user_id, db))
        needed = POOL_TARGET - available_count
        if needed <= 0:
            return
        logger.info(f"Replenishing listening pool: generating {needed} exercise(s) for user {user_id}")
        recent = (
            db.query(GeneratedPractice.topic)
            .filter(GeneratedPractice.skill == "listening", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(100)
            .all()
        )
        avoid_list = [r[0] for r in recent if r[0]]
        topic_hint = f"avoid: {', '.join(avoid_list)}" if avoid_list else ""
        for _ in range(needed):
            practice = listening_generator.generate(topic_hint)
            if practice:
                db.add(GeneratedPractice(
                    skill="listening",
                    topic=practice.get("meta", {}).get("topic", ""),
                    content=json.dumps(practice),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
    except Exception as e:
        logger.error(f"Listening replenishment error: {e}")
    finally:
        db.close()


# ── endpoints ─────────────────────────────────────────────────────────────────

@router.get("/daily-listening")
def get_daily_listening(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's active listening cards (up to 3). Deals from pool to fill slots."""
    active = _active_listening_cards(current_user.id, db)
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
        new_gps = _available_listening_for_user(current_user.id, db, limit=slots_needed, exclude_topics=active_topics)
        for gp in new_gps:
            db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
            practices.append(_with_db_id(gp))
        if new_gps:
            db.commit()

    # For VIP users, also deal full test cards (separate from practice cards)
    if current_user.role == 'vip':
        # Check if user already has an active full test
        active_full = (
            db.query(UserPractice)
            .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
            .filter(
                UserPractice.user_id == current_user.id,
                UserPractice.submitted_at.is_(None),
                GeneratedPractice.skill == "listening",
                GeneratedPractice.content.contains('"listening_full_test"'),
            )
            .all()
        )
        # Add existing active full tests to response
        for up in active_full:
            gp = db.get(GeneratedPractice, up.practice_id)
            if gp:
                practices.append(_with_db_id(gp))

        # If no active full test, deal one from pool
        if not active_full:
            served = db.query(UserPractice.practice_id).filter(UserPractice.user_id == current_user.id).subquery()
            full_test = (
                db.query(GeneratedPractice)
                .filter(
                    GeneratedPractice.skill == "listening",
                    GeneratedPractice.content.contains('"listening_full_test"'),
                    ~GeneratedPractice.id.in_(served),
                )
                .order_by(GeneratedPractice.generated_date.desc())
                .first()
            )
            if full_test:
                db.add(UserPractice(user_id=current_user.id, practice_id=full_test.id))
                db.commit()
                practices.append(_with_db_id(full_test))

    background_tasks.add_task(_replenish_listening, current_user.id)
    return {"practices": practices}


@router.post("/generate-more-listening")
def generate_more_listening(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pop 1 listening practice from pool instantly."""
    active_cards = _active_listening_cards(current_user.id, db)
    if len(active_cards) >= MAX_ACTIVE_CARDS:
        return {"practices": [], "at_capacity": True}

    active_topics = [
        db.get(GeneratedPractice, up.practice_id).topic
        for up in active_cards
        if db.get(GeneratedPractice, up.practice_id) and db.get(GeneratedPractice, up.practice_id).topic
    ]
    available = _available_listening_for_user(current_user.id, db, limit=1, exclude_topics=active_topics)
    if not available:
        background_tasks.add_task(_replenish_listening, current_user.id)
        return {"practices": [], "pool_empty": True}

    gp = available[0]
    db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
    db.commit()

    background_tasks.add_task(_replenish_listening, current_user.id)
    return {"practices": [_with_db_id(gp)]}


class SubmitAIListeningBody(BaseModel):
    practice_id: int
    user_answers: str
    score: float
    correct_count: int
    total_questions: int


@router.post("/submit-ai-listening")
def submit_ai_listening(
    body: SubmitAIListeningBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an AI listening exercise as completed for this user."""
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

    background_tasks.add_task(_replenish_listening, current_user.id)
    return {"ok": True}


class TTSRequest(BaseModel):
    text: str
    voice: str = "british_female"


@router.post("/tts-preview")
def tts_preview(
    body: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """Convert text to speech and return the audio URL. For testing TTS integration."""
    from app.services.tts import synthesize, VOICES

    text = body.text
    voice = body.voice
    if voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown voice. Choose from: {list(VOICES.keys())}")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 chars)")
    try:
        audio_url = synthesize(text, voice)
        return {"audio_url": audio_url}
    except Exception as e:
        logger.error("TTS failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.post("/generate-listening")
def generate_listening_practice(
    count: int = 1,
    topic_hint: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate N listening exercises into global pool (with TTS audio)."""
    generated = []
    for _ in range(count):
        practice = listening_generator.generate(topic_hint)
        if practice:
            db.add(GeneratedPractice(
                skill="listening",
                topic=practice.get("meta", {}).get("topic", ""),
                content=json.dumps(practice),
                is_validated=True,
                generated_date=datetime.utcnow(),
            ))
            generated.append(practice)
    db.commit()
    return {"generated": len(generated), "practices": generated}
