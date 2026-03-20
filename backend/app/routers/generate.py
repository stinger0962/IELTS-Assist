import hashlib
import json
import logging
import random
import time
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from openai import OpenAI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, Topic, User, UserPractice
from app.services.ai.practice_generator import practice_generator
from app.services.ai.listening_generator import listening_generator
from app.services.ai.grammar_generator import grammar_generator
from app.services.ai.writing_config import generate_metadata as writing_generate_metadata
from app.services.ai.writing_grader import WritingGrader
from app.services.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ACTIVE_CARDS = 3
POOL_TARGET = 5


# ── helpers ───────────────────────────────────────────────────────────────────

def _active_cards(user_id: int, db: Session, skill: str = "reading") -> list:
    return (
        db.query(UserPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at.is_(None),
            GeneratedPractice.skill == skill,
        )
        .all()
    )


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
            .limit(100)
            .all()
        )
        avoid_list = [r[0] for r in recent if r[0]]
        for _ in range(needed):
            practice = practice_generator.generate_practice(avoid_topics=avoid_list)
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
    """Cron job: add 3 reading + 2 listening + 2 grammar + 2 writing exercises to global pool at midnight UTC."""
    db = SessionLocal()
    try:
        # Reading exercises
        logger.info("Daily generation: adding 3 reading exercises")
        recent_reading = (
            db.query(GeneratedPractice.topic)
            .filter(GeneratedPractice.skill == "reading", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(100)
            .all()
        )
        reading_avoid = [r[0] for r in recent_reading if r[0]]
        for _ in range(3):
            practice = practice_generator.generate_practice(avoid_topics=reading_avoid)
            if practice:
                db.add(GeneratedPractice(
                    skill="reading",
                    topic=practice.get("meta", {}).get("topic", ""),
                    content=json.dumps(practice),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
        logger.info("Daily reading generation complete")

        # Listening exercises
        logger.info("Daily generation: adding 2 listening exercises")
        recent = (
            db.query(GeneratedPractice.topic)
            .filter(GeneratedPractice.skill == "listening", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(100)
            .all()
        )
        avoid_list = [r[0] for r in recent if r[0]]
        topic_hint = f"avoid: {', '.join(avoid_list)}" if avoid_list else ""
        # Generate 1 conversation/discussion + 1 monologue/lecture for format variety
        formats = [random.choice(["conversation", "discussion"]),
                   random.choice(["monologue", "lecture"])]
        for fmt in formats:
            practice = listening_generator.generate(topic_hint, format_hint=fmt)
            if practice:
                db.add(GeneratedPractice(
                    skill="listening",
                    topic=practice.get("meta", {}).get("topic", ""),
                    content=json.dumps(practice),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
        logger.info("Daily listening generation complete")

        # Grammar exercises
        logger.info("Daily generation: adding 2 grammar exercises")
        recent_grammar = (
            db.query(GeneratedPractice.topic)
            .filter(GeneratedPractice.skill == "grammar", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(60)
            .all()
        )
        grammar_avoid = [r[0] for r in recent_grammar if r[0]]
        # Rotate bands so daily batch covers different levels
        bands = ["band_5_6", "band_6_7", "band_7_8"]
        random.shuffle(bands)
        for i in range(2):
            practice = grammar_generator.generate(
                avoid_topics=grammar_avoid,
                prefer_band=bands[i],
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
        logger.info("Daily grammar generation complete")

        # Writing prompts (instant — no GPT call, just pick from hardcoded bank)
        logger.info("Daily generation: adding 2 writing prompts")
        recent_writing = (
            db.query(GeneratedPractice)
            .filter(GeneratedPractice.skill == "writing", GeneratedPractice.topic.isnot(None))
            .order_by(GeneratedPractice.generated_date.desc())
            .limit(30)
            .all()
        )
        writing_avoid_topics = [r.topic for r in recent_writing if r.topic]
        writing_avoid_domains = []
        writing_avoid_types = []
        for r in recent_writing[:10]:
            try:
                c = json.loads(r.content)
                meta = c.get("meta", {})
                if meta.get("domain"):
                    writing_avoid_domains.append(meta["domain"])
                if meta.get("essay_type"):
                    writing_avoid_types.append(meta["essay_type"])
            except Exception:
                pass
        for _ in range(2):
            prompt_data = writing_generate_metadata(
                avoid_topics=writing_avoid_topics,
                avoid_domains=writing_avoid_domains,
                avoid_types=writing_avoid_types,
            )
            if prompt_data:
                content = {
                    "meta": {
                        "module": "writing_task2",
                        "essay_type": prompt_data["essay_type"],
                        "domain": prompt_data["domain"],
                        "topic": prompt_data["statement"][:60],
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
                    topic=prompt_data["statement"][:60],
                    content=json.dumps(content),
                    is_validated=True,
                    generated_date=datetime.utcnow(),
                ))
        db.commit()
        logger.info("Daily writing generation complete")
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

class WrongAnswerItem(BaseModel):
    key: str           # e.g. "tfng_3" or "mc_1" — used to map response back to UI
    question_type: str # "T/F/NG" or "MCQ"
    question: str
    user_answer: str
    correct_answer: str


class ExplainMistakesBody(BaseModel):
    passage: str
    wrong_answers: list[WrongAnswerItem]


@router.post("/explain-mistakes")
def explain_mistakes(
    body: ExplainMistakesBody,
    current_user: User = Depends(get_current_user),
):
    """Return a one-sentence explanation for each wrong answer, grounded in the passage."""
    if not body.wrong_answers:
        return {"explanations": []}

    lines = []
    for i, w in enumerate(body.wrong_answers, 1):
        lines.append(
            f'{i}. key="{w.key}" | Type: {w.question_type} | '
            f'Question: "{w.question}" | You answered: {w.user_answer} | Correct: {w.correct_answer}'
        )

    prompt = (
        "You are an IELTS reading teacher. Using only the passage below, write ONE concise sentence "
        "for each wrong answer explaining why the correct answer is right. "
        "Be specific — quote or paraphrase the relevant part of the passage.\n\n"
        f"PASSAGE:\n{body.passage[:3500]}\n\n"
        "WRONG ANSWERS:\n" + "\n".join(lines) + "\n\n"
        'Return ONLY a JSON array: [{"key": "...", "explanation": "..."}, ...]'
    )
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return {"explanations": data}
    except Exception as e:
        logger.error(f"Explain mistakes error: {e}")
        return {"explanations": []}


class TranslateDefinitionBody(BaseModel):
    word: str
    content_en: str


@router.post("/translate-definition")
def translate_definition(
    body: TranslateDefinitionBody,
    current_user: User = Depends(get_current_user),
):
    """Translate an English vocabulary definition to Chinese via Youdao API."""
    try:
        salt = str(uuid.uuid4())
        curtime = str(int(time.time()))
        q = body.content_en
        # Youdao v3 sign: truncate input if longer than 20 chars
        input_str = q if len(q) <= 20 else q[:10] + str(len(q)) + q[-10:]
        sign = hashlib.sha256(
            (settings.YOUDAO_APP_KEY + input_str + salt + curtime + settings.YOUDAO_APP_SECRET).encode("utf-8")
        ).hexdigest()
        resp = httpx.post(
            "https://openapi.youdao.com/api",
            data={
                "q": q,
                "from": "en",
                "to": "zh-CHS",
                "appKey": settings.YOUDAO_APP_KEY,
                "salt": salt,
                "sign": sign,
                "signType": "v3",
                "curtime": curtime,
            },
            timeout=8.0,
        )
        result = resp.json()
        if result.get("errorCode") == "0" and result.get("translation"):
            return {"content_zh": result["translation"][0]}
        logger.error("Youdao translate-definition errorCode=%s", result.get("errorCode"))
        return {"content_zh": ""}
    except Exception as e:
        logger.error(f"translate_definition error: {e}")
        return {"content_zh": ""}


class ExtractVocabularyBody(BaseModel):
    passage: str
    topic: str


@router.post("/extract-vocabulary")
def extract_vocabulary(
    body: ExtractVocabularyBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Extract 3-5 IELTS academic vocabulary items from a reading passage and save as Topics."""
    prompt = (
        "You are an IELTS vocabulary expert. Extract exactly 5 high-value IELTS Academic "
        "vocabulary words or phrases from the passage below. "
        "Return a JSON array of objects with keys: title, content (definition in simple English), example (a new example sentence). "
        "Return ONLY the JSON array, no extra text.\n\n"
        f"Topic: {body.topic}\n\nPassage:\n{body.passage[:3000]}"
    )
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        items = data if isinstance(data, list) else data.get("items", data.get("words", []))
    except Exception as e:
        logger.error(f"Vocabulary extraction error: {e}")
        return {"extracted": 0}

    count = 0
    for item in items[:5]:
        title = item.get("title", "").strip()
        content = item.get("content", "").strip()
        example = item.get("example", "").strip()
        if not title or not content:
            continue
        db.add(Topic(
            user_id=current_user.id,
            skill="reading",
            category="vocabulary",
            title=title,
            content=content,
            example=example or None,
            difficulty=3,
        ))
        count += 1
    if count:
        db.commit()
    return {"extracted": count}


class TTSRequest(BaseModel):
    text: str
    voice: str = "british_female"


# ── listening pool helpers ────────────────────────────────────────────────────

def _available_listening_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    """Global listening pool practices not yet dealt to this user."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id
    ).subquery()
    q = (
        db.query(GeneratedPractice)
        .filter(
            GeneratedPractice.skill == "listening",
            ~GeneratedPractice.id.in_(served),
        )
        .order_by(GeneratedPractice.generated_date.asc())
    )
    if exclude_topics:
        filtered = [t for t in exclude_topics if t]
        if filtered:
            q = q.filter(~GeneratedPractice.topic.in_(filtered))
    return q.limit(limit).all() if limit else q.all()


def _active_listening_cards(user_id: int, db: Session) -> list:
    """Active (unsubmitted) listening cards for this user."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id,
        UserPractice.submitted_at.is_(None),
    ).subquery()
    return (
        db.query(UserPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at.is_(None),
            GeneratedPractice.skill == "listening",
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


# ── listening endpoints ──────────────────────────────────────────────────────

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


@router.post("/tts-preview")
def tts_preview(
    body: TTSRequest,
    current_user: User = Depends(get_current_user),
):
    """Convert text to speech and return the audio URL. For testing TTS integration."""
    from app.services.tts import synthesize, VOICES

    if body.voice not in VOICES:
        raise HTTPException(status_code=400, detail=f"Unknown voice. Choose from: {list(VOICES.keys())}")
    if len(body.text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 chars)")
    try:
        audio_url = synthesize(body.text, body.voice)
        return {"audio_url": audio_url}
    except Exception as e:
        logger.error("TTS failed: %s", e)
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.post("/generate-reading")
def generate_reading_practice(
    count: int = 3,
    topic_hint: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Admin: force-generate N exercises into global pool."""
    avoid_topics = [t.strip() for t in topic_hint.replace("avoid:", "").split(",") if t.strip()] if topic_hint else None
    generated = []
    for _ in range(count):
        practice = practice_generator.generate_practice(avoid_topics=avoid_topics)
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


# ── grammar pool helpers ─────────────────────────────────────────────────────

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


# ── grammar endpoints ────────────────────────────────────────────────────────

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


@router.post("/generate-more-grammar")
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
                        "topic": prompt_data["statement"][:60],
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
                    topic=prompt_data["statement"][:60],
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
                    "topic": prompt_data["statement"][:60],
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
                topic=prompt_data["statement"][:60],
                content=json.dumps(content),
                is_validated=True,
                generated_date=datetime.utcnow(),
            ))
    db.commit()


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


@router.post("/submit-ai-writing")
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


@router.post("/generate-grammar")
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
