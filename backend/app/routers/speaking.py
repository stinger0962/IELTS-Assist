"""Speaking skill — pool helpers + endpoints.

Pool seeding is instant (cue cards from config, no GPT).
Submit endpoint handles audio upload → Whisper → Azure PA → GPT-4o grading.
"""
import json
import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
# Lazy import pydub to avoid audioop issues in test environments
# from pydub import AudioSegment

from app.config import settings
from app.database import SessionLocal, get_db
from app.models.models import GeneratedPractice, User, UserPractice
from app.services.ai.speaking_config import PART2_CUE_CARDS, generate_metadata as speaking_generate_metadata
from app.services.ai.speaking_grader import SpeakingGrader
from app.services.azure_speech import assess_pronunciation
from app.services.auth import get_current_user

from openai import OpenAI

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_ACTIVE_CARDS = 3
POOL_TARGET = 5
SPEAKING_AUDIO_DIR = Path(settings.TTS_AUDIO_DIR) / "speaking"


def _with_db_id(practice: GeneratedPractice) -> dict:
    content = json.loads(practice.content)
    content["practice_db_id"] = practice.id
    return content


# ── pool helpers ─────────────────────────────────────────────────────────────

def _available_speaking_for_user(user_id: int, db: Session, limit: int = None, exclude_topics: list = None):
    """Global speaking pool practices not yet dealt to this user."""
    served = db.query(UserPractice.practice_id).filter(
        UserPractice.user_id == user_id
    ).subquery()
    q = db.query(GeneratedPractice).filter(
        GeneratedPractice.skill == "speaking",
        GeneratedPractice.is_validated == True,
        ~GeneratedPractice.id.in_(served),
    )
    if exclude_topics:
        filtered = [t for t in exclude_topics if t]
        if filtered:
            q = q.filter(~GeneratedPractice.topic.in_(filtered))
    q = q.order_by(GeneratedPractice.generated_date)
    return q.limit(limit).all() if limit else q.all()


def _active_speaking_cards(user_id: int, db: Session) -> list:
    """Active (unsubmitted) speaking cards for this user."""
    return (
        db.query(UserPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == user_id,
            UserPractice.submitted_at.is_(None),
            GeneratedPractice.skill == "speaking",
        )
        .all()
    )


def _seed_speaking_pool(db: Session, count: int = 5) -> None:
    """Seed pool from hardcoded cue cards (instant, no GPT)."""
    existing_topics = {
        gp.topic for gp in db.query(GeneratedPractice).filter(
            GeneratedPractice.skill == "speaking"
        ).all()
    }
    added = 0
    for card in PART2_CUE_CARDS:
        if card["topic_title"] in existing_topics:
            continue
        content = {
            "meta": {
                "module": "speaking_part2",
                "domain": card["domain"],
                "topic": card["topic_title"],
            },
            "cue_card": {
                "topic_line": card["topic_line"],
                "bullets": card["bullets"],
                "follow_up": card["follow_up"],
            },
            "cue_card_metadata": card,
        }
        db.add(GeneratedPractice(
            skill="speaking",
            topic=card["topic_title"],
            content=json.dumps(content),
            is_validated=True,
            generated_date=datetime.utcnow(),
        ))
        added += 1
        if added >= count:
            break
    if added:
        db.commit()


# ── endpoints ────────────────────────────────────────────────────────────────

@router.get("/daily-speaking")
def get_daily_speaking(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return user's active speaking cards (up to 3). Deals from pool to fill slots."""
    active = _active_speaking_cards(current_user.id, db)
    practices = [_with_db_id(db.get(GeneratedPractice, up.practice_id))
                 for up in active
                 if db.get(GeneratedPractice, up.practice_id)]

    slots_needed = MAX_ACTIVE_CARDS - len(practices)
    if slots_needed > 0:
        # Seed pool if empty
        pool = _available_speaking_for_user(current_user.id, db, limit=1)
        if not pool:
            _seed_speaking_pool(db)
            pool = _available_speaking_for_user(current_user.id, db, limit=1)

        active_topics = [
            db.get(GeneratedPractice, up.practice_id).topic
            for up in active
            if db.get(GeneratedPractice, up.practice_id) and db.get(GeneratedPractice, up.practice_id).topic
        ]
        new_gps = _available_speaking_for_user(
            current_user.id, db, limit=slots_needed, exclude_topics=active_topics,
        )
        for gp in new_gps:
            db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
            practices.append(_with_db_id(gp))
        if new_gps:
            db.commit()

    return {"practices": practices}


@router.post("/generate-more-speaking")
def generate_more_speaking(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pop 1 speaking practice from pool instantly."""
    active = _active_speaking_cards(current_user.id, db)
    if len(active) >= MAX_ACTIVE_CARDS:
        practices = [_with_db_id(db.get(GeneratedPractice, up.practice_id))
                     for up in active if db.get(GeneratedPractice, up.practice_id)]
        return {"practices": practices, "pool_empty": False, "at_capacity": True}

    pool = _available_speaking_for_user(current_user.id, db, limit=1)
    if not pool:
        _seed_speaking_pool(db, count=5)
        pool = _available_speaking_for_user(current_user.id, db, limit=1)
    if not pool:
        practices = [_with_db_id(db.get(GeneratedPractice, up.practice_id))
                     for up in active if db.get(GeneratedPractice, up.practice_id)]
        return {"practices": practices, "pool_empty": True, "at_capacity": False}

    gp = pool[0]
    db.add(UserPractice(user_id=current_user.id, practice_id=gp.id))
    db.commit()

    active = _active_speaking_cards(current_user.id, db)
    practices = [_with_db_id(db.get(GeneratedPractice, up.practice_id))
                 for up in active if db.get(GeneratedPractice, up.practice_id)]
    return {"practices": practices, "pool_empty": False, "at_capacity": False}


@router.post("/submit-ai-speaking")
async def submit_ai_speaking(
    audio: UploadFile = File(...),
    practice_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload audio → Whisper transcribe → Azure PA → GPT-4o grade."""
    # Find the user practice
    up = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == practice_id,
        UserPractice.submitted_at.is_(None),
    ).first()
    if not up:
        raise HTTPException(404, "Practice not found or already submitted")

    gp = db.query(GeneratedPractice).get(up.practice_id)
    content = json.loads(gp.content)
    cue_card = content.get("cue_card", {})

    # Save uploaded audio to temp file
    SPEAKING_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_bytes = await audio.read()

    # Reject if too small (~5 seconds of audio ≈ 50KB for webm)
    if len(audio_bytes) < 10_000:
        raise HTTPException(422, "Audio too short. Please record at least 5 seconds.")

    # Convert to WAV for Azure PA
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp_in:
        tmp_in.write(audio_bytes)
        tmp_in_path = tmp_in.name

    wav_path = str(SPEAKING_AUDIO_DIR / f"{current_user.id}_{practice_id}.wav")
    try:
        from pydub import AudioSegment
        audio_segment = AudioSegment.from_file(tmp_in_path)
        audio_segment.export(wav_path, format="wav")
    except Exception as e:
        logger.error(f"Audio conversion failed: {e}")
        raise HTTPException(422, f"Audio conversion failed. Please try a different recording.")
    finally:
        Path(tmp_in_path).unlink(missing_ok=True)

    # Steps 1+2: Whisper transcription + Azure PA in PARALLEL (both read the WAV independently)
    wav_size = Path(wav_path).stat().st_size
    logger.info(f"[Speaking] Starting parallel pipeline for user {current_user.id}, wav size={wav_size}")

    transcript = None
    whisper_error = None
    azure_scores = None

    def run_whisper():
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        with open(wav_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
        return result.strip() if isinstance(result, str) else result.text.strip()

    def run_azure_pa():
        return assess_pronunciation(wav_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        whisper_future = executor.submit(run_whisper)
        azure_future = executor.submit(run_azure_pa)

        # Collect Whisper result (required)
        try:
            transcript = whisper_future.result(timeout=60)
            logger.info(f"[Speaking] Whisper OK: {len(transcript)} chars, first 100: {transcript[:100]}")
        except Exception as e:
            whisper_error = e
            logger.error(f"[Speaking] Whisper FAILED: {e}")

        # Collect Azure PA result (optional — graceful failure)
        try:
            azure_scores = azure_future.result(timeout=120)
            if azure_scores:
                logger.info(f"[Speaking] Azure PA OK: accuracy={azure_scores['accuracy_score']}, fluency={azure_scores['fluency_score']}, pronunciation={azure_scores['pronunciation_score']}, words={len(azure_scores.get('words', []))}")
            else:
                logger.warning("[Speaking] Azure PA returned None (key missing or no utterances)")
        except Exception as e:
            logger.warning(f"[Speaking] Azure PA FAILED (proceeding without pronunciation): {e}")

    if whisper_error or not transcript:
        Path(wav_path).unlink(missing_ok=True)
        raise HTTPException(500, "Transcription failed. Please try again.")

    if len(transcript) < 10:
        logger.warning(f"[Speaking] Transcript too short: '{transcript}'")
        Path(wav_path).unlink(missing_ok=True)
        raise HTTPException(422, "No speech detected. Please speak clearly and try again.")

    # Step 3: GPT-4o-mini grading (fast — 3-5s)
    try:
        logger.info(f"[Speaking] Step 3: GPT-4o-mini grading, transcript={len(transcript)} chars, azure={'yes' if azure_scores else 'no'}")
        grader = SpeakingGrader()
        grading_result = grader.grade(transcript, cue_card, azure_scores)
        logger.info(f"[Speaking] GPT-4o-mini OK: overall_band={grading_result.get('examiner_result', {}).get('overall_band', '?')}")
    except Exception as e:
        logger.error(f"[Speaking] GPT-4o-mini grading FAILED: {e}", exc_info=True)
        Path(wav_path).unlink(missing_ok=True)
        raise HTTPException(500, "Grading failed. Please try again.")

    # Store results
    overall = grading_result.get("examiner_result", {}).get("overall_band", 0)
    grading_result["transcript"] = transcript
    if azure_scores:
        # Only store mispronounced words to reduce storage size
        grading_result["pronunciation_words"] = [
            w for w in azure_scores.get("words", [])
            if w.get("error_type") not in ("None", None)
        ]

    up.submitted_at = datetime.utcnow()
    up.user_answers = json.dumps(grading_result)
    up.score = overall
    db.commit()

    # Clean up audio file (results stored, no need to keep)
    Path(wav_path).unlink(missing_ok=True)

    return grading_result
