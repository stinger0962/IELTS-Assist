"""Shared generate endpoints + daily cron job.

Skill-specific pool helpers and endpoints live in their own routers:
  reading.py, listening.py, grammar.py, writing.py
"""
import json
import logging
import random
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.ai.llm import chat_json
from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, Topic, User, UserPractice, VocabCache
from app.services import vocab
from app.services import quota as quota_service
from app.services.auth import get_current_user
from app.services.quota import quota

# Skill-specific generators (used by daily_generate)
from app.services.ai.practice_generator import practice_generator
from app.services.ai.listening_generator import listening_generator
from app.services.ai.grammar_generator import grammar_generator
from app.services.ai.writing_config import generate_metadata as writing_generate_metadata

router = APIRouter()
logger = logging.getLogger(__name__)


# ── daily cron ────────────────────────────────────────────────────────────────

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
        logger.info("Daily writing generation complete")
    except Exception as e:
        logger.error(f"Daily generation error: {e}")
    finally:
        db.close()


# ── shared endpoints ──────────────────────────────────────────────────────────

class WrongAnswerItem(BaseModel):
    key: str           # e.g. "tfng_3" or "mc_1" — used to map response back to UI
    question_type: str # "T/F/NG" or "MCQ"
    question: str
    user_answer: str
    correct_answer: str


class ExplainMistakesBody(BaseModel):
    passage: str
    wrong_answers: list[WrongAnswerItem]


@router.post("/explain-mistakes", dependencies=[Depends(quota("lookup"))])
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
        raw = chat_json(
            tier="utility",
            messages=[{"role": "user", "content": prompt}],
            max_output_tokens=1500,
            temperature=0.2,
            reasoning_effort="low",
            json_mode=False,  # prompt asks for a bare JSON array
        ).strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return {"explanations": data}
    except Exception as e:
        logger.error(f"Explain mistakes error: {e}")
        return {"explanations": []}


TRANSLATE_PROMPT = (
    "You help Chinese-speaking IELTS students.\n"
    "Translate the given English text into natural Simplified Chinese.\n"
    "Keep it concise and faithful. No pinyin, no commentary, no English restated.\n"
    'Return JSON of the form {"text_zh": "<translation>"}.'
)


class TranslateBody(BaseModel):
    text: str


@router.post("/translate", dependencies=[Depends(quota("lookup"))])
def translate(
    body: TranslateBody,
    current_user: User = Depends(get_current_user),
):
    """General English→Chinese translation for UI copy such as grammar tips.

    Vocabulary definitions do NOT use this — /define-word returns Chinese in the
    same response, saving a second round trip.
    """
    try:
        raw = chat_json(
            tier="utility",
            messages=[
                {"role": "system", "content": TRANSLATE_PROMPT},
                {"role": "user", "content": body.text},
            ],
            max_output_tokens=600,
            reasoning_effort="low",
        )
        return {"text_zh": (json.loads(raw).get("text_zh") or "").strip()}
    except Exception as e:
        logger.error(f"translate error: {e}")
        return {"text_zh": ""}


class DefineWordBody(BaseModel):
    word: str
    context: str | None = None


@router.post("/define-word", dependencies=[Depends(quota("lookup"))])
def define_word(
    body: DefineWordBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Definition + Chinese + IPA + self-hosted audio, cached globally by word.

    Supersedes both the browser's direct dictionaryapi.dev calls and the separate
    translate-definition endpoint: one round trip now returns everything, the
    audio is hosted by us, and the cache is shared across all users.
    """
    key = vocab.normalise(body.word)
    if not key:
        raise HTTPException(status_code=400, detail="word is required")

    cached = db.query(VocabCache).filter(VocabCache.word == key).first()
    if cached:
        # Served from cache — cost nothing, so give the quota back. Charging for
        # a free response would penalise exactly the behaviour we want.
        quota_service.refund(db, current_user.id, "lookup")
        return {
            "word": cached.word,
            "definition_en": cached.definition_en,
            "definition_zh": cached.definition_zh,
            "example": cached.example,
            "phonetic": cached.phonetic,
            "audio_url": cached.audio_url,
            "cached": True,
        }

    try:
        entry = vocab.generate_entry(body.word, body.context)
    except Exception as e:
        logger.error("define_word failed for %r: %s", key, e)
        raise HTTPException(status_code=502, detail="lookup unavailable")

    entry["audio_url"] = vocab.synthesize_pronunciation(key)

    db.add(VocabCache(word=key, **entry))
    try:
        db.commit()
    except Exception:
        # Another request cached the same word first — harmless.
        db.rollback()

    return {"word": key, **entry, "cached": False}


class ExtractVocabularyBody(BaseModel):
    passage: str
    topic: str


@router.post("/extract-vocabulary", dependencies=[Depends(quota("lookup"))])
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
        raw = chat_json(
            tier="utility",
            messages=[{"role": "user", "content": prompt}],
            max_output_tokens=1500,
            temperature=0.3,
            reasoning_effort="low",
            json_mode=False,  # prompt asks for a bare JSON array
        ).strip()
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
