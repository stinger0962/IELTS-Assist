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
from app.services.ai.speaking_config import PART2_CUE_CARDS, generate_metadata as speaking_generate_metadata, generate_metadata_part1, generate_metadata_part3
from app.services.ai.speaking_grader import SpeakingGrader
from app.services.azure_speech import assess_pronunciation
from app.services.auth import get_current_user
from app.services.quota import quota

from app.services.ai.llm import get_client

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


def _seed_speaking_pool(db: Session, count: int = 6) -> None:
    """Seed pool with balanced Part 1 + Part 2 + Part 3 + Full Test exercises (instant, no GPT).

    Rotates across all parts, seeding whichever has fewest.
    """
    existing = db.query(GeneratedPractice).filter(
        GeneratedPractice.skill == "speaking"
    ).all()
    existing_topics = {gp.topic for gp in existing}

    # Count existing parts
    counts = {
        "part1": sum(1 for gp in existing if '"speaking_part1"' in (gp.content or "")),
        "part2": sum(1 for gp in existing if '"speaking_part2"' in (gp.content or "")),
        "part3": sum(1 for gp in existing if '"speaking_part3"' in (gp.content or "")),
        "full_test": sum(1 for gp in existing if '"speaking_full_test"' in (gp.content or "")),
    }

    def seed_part1():
        meta = generate_metadata_part1(avoid_topics=list(existing_topics))
        if not meta:
            return False
        content = {"meta": {"module": "speaking_part1", "topic": meta["topic_title"]}, "topics": meta["topics"]}
        db.add(GeneratedPractice(skill="speaking", topic=meta["topic_title"], content=json.dumps(content), is_validated=True, generated_date=datetime.utcnow()))
        existing_topics.add(meta["topic_title"])
        counts["part1"] += 1
        return True

    def seed_part2():
        for card in PART2_CUE_CARDS:
            if card["topic_title"] not in existing_topics:
                content = {"meta": {"module": "speaking_part2", "domain": card["domain"], "topic": card["topic_title"]}, "cue_card": {"topic_line": card["topic_line"], "bullets": card["bullets"], "follow_up": card["follow_up"]}, "cue_card_metadata": card}
                db.add(GeneratedPractice(skill="speaking", topic=card["topic_title"], content=json.dumps(content), is_validated=True, generated_date=datetime.utcnow()))
                existing_topics.add(card["topic_title"])
                counts["part2"] += 1
                return True
        return False

    def seed_part3():
        meta = generate_metadata_part3(avoid_topics=list(existing_topics))
        if not meta:
            return False
        content = {"meta": {"module": "speaking_part3", "topic": meta["topic_title"]}, "topics": meta["topics"]}
        db.add(GeneratedPractice(skill="speaking", topic=meta["topic_title"], content=json.dumps(content), is_validated=True, generated_date=datetime.utcnow()))
        existing_topics.add(meta["topic_title"])
        counts["part3"] += 1
        return True

    def seed_full_test():
        # Bundle: 3 random Part 1 topics + 1 Part 2 cue card + 1 Part 3 theme
        p1 = generate_metadata_part1(avoid_topics=list(existing_topics))
        if not p1:
            return False
        # Find an unused Part 2 cue card
        p2_card = None
        for card in PART2_CUE_CARDS:
            if card["topic_title"] not in existing_topics:
                p2_card = card
                break
        if not p2_card:
            p2_card = PART2_CUE_CARDS[0]  # fallback
        p3 = generate_metadata_part3(avoid_topics=list(existing_topics))
        if not p3:
            return False

        topic_title = f"Full Test: {p1['topic_title'][:20]} + {p2_card['topic_title'][:20]}"
        content = {
            "meta": {"module": "speaking_full_test", "topic": topic_title},
            "part1": {"topics": p1["topics"]},
            "part2": {
                "cue_card": {
                    "topic_line": p2_card["topic_line"],
                    "bullets": p2_card["bullets"],
                    "follow_up": p2_card["follow_up"],
                },
                "cue_card_metadata": p2_card,
            },
            "part3": {"topics": p3["topics"]},
        }
        db.add(GeneratedPractice(
            skill="speaking", topic=topic_title,
            content=json.dumps(content), is_validated=True,
            generated_date=datetime.utcnow(),
        ))
        existing_topics.add(topic_title)
        counts["full_test"] += 1
        return True

    seeders = {"part1": seed_part1, "part2": seed_part2, "part3": seed_part3, "full_test": seed_full_test}
    added = 0
    for _ in range(count):
        # Seed whichever part has fewest
        min_part = min(counts, key=counts.get)
        if not seeders[min_part]():
            # Fallback: try others
            for part, fn in seeders.items():
                if part != min_part and fn():
                    break
        added += 1

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


@router.post("/submit-ai-speaking", dependencies=[Depends(quota("grade"))])
async def submit_ai_speaking(
    audio: UploadFile = File(...),
    practice_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Layer 1: Upload audio → Whisper transcribe → GPT-4o grade. Fast (~15s).

    Skips Azure PA for speed. Pronunciation band estimated by GPT from transcript.
    Audio file is saved for optional Layer 2 pronunciation analysis later.
    """
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

    # Save uploaded audio
    SPEAKING_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_bytes = await audio.read()

    if len(audio_bytes) < 10_000:
        raise HTTPException(422, "Audio too short. Please record at least 5 seconds.")

    # Save original webm/mp4 for both Whisper and future Azure PA
    audio_path = str(SPEAKING_AUDIO_DIR / f"{current_user.id}_{up.id}.webm")
    Path(audio_path).write_bytes(audio_bytes)
    logger.info(f"[Speaking] Audio saved: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.0f}KB)")

    # Step 1: Whisper transcription (send original webm — much smaller than WAV)
    logger.info(f"[Speaking] Step 1: Whisper transcription for user {current_user.id}")
    client = get_client()
    try:
        with open(audio_path, "rb") as f:
            whisper_result = client.audio.transcriptions.create(
                model=settings.OPENAI_MODEL_TRANSCRIBE,
                file=f,
                response_format="text",
            )
        transcript = whisper_result.strip() if isinstance(whisper_result, str) else whisper_result.text.strip()
        logger.info(f"[Speaking] Whisper OK: {len(transcript)} chars, first 100: {transcript[:100]}")
    except Exception as e:
        logger.error(f"[Speaking] Whisper FAILED: {e}")
        Path(audio_path).unlink(missing_ok=True)
        raise HTTPException(500, "Transcription failed. Please try again.")

    if not transcript or len(transcript) < 10:
        logger.warning(f"[Speaking] Transcript too short: '{transcript}'")
        Path(audio_path).unlink(missing_ok=True)
        raise HTTPException(422, "No speech detected. Please speak clearly and try again.")

    # Step 2: GPT-4o grading (no Azure PA — pronunciation estimated from transcript)
    try:
        logger.info(f"[Speaking] Step 2: GPT-4o grading, transcript={len(transcript)} chars")
        grader = SpeakingGrader()
        grading_result = grader.grade(transcript, cue_card, azure_scores=None)
        logger.info(f"[Speaking] GPT-4o OK: overall_band={grading_result.get('examiner_result', {}).get('overall_band', '?')}")
    except Exception as e:
        logger.error(f"[Speaking] GPT-4o grading FAILED: {e}", exc_info=True)
        Path(audio_path).unlink(missing_ok=True)
        raise HTTPException(500, "Grading failed. Please try again.")

    # Store results — keep audio_path for Layer 2 pronunciation analysis
    overall = grading_result.get("examiner_result", {}).get("overall_band", 0)
    grading_result["transcript"] = transcript
    grading_result["has_pronunciation_analysis"] = False
    grading_result["audio_path"] = audio_path

    up.submitted_at = datetime.utcnow()
    up.user_answers = json.dumps(grading_result)
    up.score = overall
    db.commit()

    return grading_result


@router.post("/analyze-pronunciation", dependencies=[Depends(quota("grade"))])
def analyze_pronunciation(
    practice_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Layer 2: Run Azure PA on saved audio. On-demand, ~30-60s.

    Updates the stored grading result with real pronunciation scores
    and per-word accuracy data. Replaces GPT's pronunciation estimate.
    """
    up = db.query(UserPractice).filter(
        UserPractice.user_id == current_user.id,
        UserPractice.practice_id == practice_id,
        UserPractice.submitted_at.isnot(None),
    ).first()
    if not up or not up.user_answers:
        raise HTTPException(404, "Submitted practice not found")

    grading_result = json.loads(up.user_answers)

    # Already analyzed?
    if grading_result.get("has_pronunciation_analysis"):
        return {
            "pronunciation_band": grading_result["examiner_result"]["pronunciation"]["band"],
            "azure_scores": grading_result["examiner_result"]["pronunciation"].get("azure_scores"),
            "pronunciation_words": grading_result.get("pronunciation_words", []),
            "overall_band": grading_result["examiner_result"]["overall_band"],
        }

    # Find saved audio file
    audio_path = grading_result.get("audio_path", "")
    if not audio_path or not Path(audio_path).exists():
        raise HTTPException(404, "Audio file not found. Pronunciation analysis is only available for recent recordings.")

    # Convert webm → WAV for Azure PA
    wav_path = audio_path.replace(".webm", ".wav")
    try:
        from pydub import AudioSegment
        audio_segment = AudioSegment.from_file(audio_path)
        audio_segment.export(wav_path, format="wav")
        logger.info(f"[Speaking] Pronunciation: converted to WAV, size={Path(wav_path).stat().st_size}")
    except Exception as e:
        logger.error(f"[Speaking] Pronunciation: WAV conversion failed: {e}")
        raise HTTPException(500, "Audio conversion failed.")

    # Run Azure PA
    logger.info(f"[Speaking] Pronunciation: starting Azure PA for user {current_user.id}")
    try:
        azure_scores = assess_pronunciation(wav_path)
    except Exception as e:
        logger.error(f"[Speaking] Pronunciation: Azure PA failed: {e}")
        Path(wav_path).unlink(missing_ok=True)
        raise HTTPException(500, "Pronunciation analysis failed. Please try again.")
    finally:
        Path(wav_path).unlink(missing_ok=True)

    if not azure_scores:
        raise HTTPException(500, "Pronunciation analysis returned no results.")

    logger.info(f"[Speaking] Pronunciation OK: accuracy={azure_scores['accuracy_score']}, fluency={azure_scores['fluency_score']}, pronunciation={azure_scores['pronunciation_score']}")

    # Replace GPT pronunciation estimate with real Azure data (no blending)
    grader = SpeakingGrader()
    new_pron_band = grader._map_pronunciation_band(azure_scores["pronunciation_score"])
    er = grading_result.get("examiner_result", {})
    old_pron_band = er.get("pronunciation", {}).get("band", 0)
    old_overall = er.get("overall_band", 0)

    er["pronunciation"]["band"] = new_pron_band
    er["pronunciation"]["azure_scores"] = {
        "accuracy": azure_scores["accuracy_score"],
        "fluency": azure_scores["fluency_score"],
        "prosody": azure_scores["prosody_score"],
        "composite": azure_scores["pronunciation_score"],
    }

    # Recalculate overall band
    bands = [
        er.get("fluency_coherence", {}).get("band", 0),
        er.get("lexical_resource", {}).get("band", 0),
        er.get("grammatical_range_accuracy", {}).get("band", 0),
        new_pron_band,
    ]
    new_overall = round(sum(bands) / 4 * 2) / 2
    er["overall_band"] = new_overall

    # Store mispronounced words
    pronunciation_words = [
        w for w in azure_scores.get("words", [])
        if w.get("error_type") not in ("None", None)
    ]
    grading_result["pronunciation_words"] = pronunciation_words
    grading_result["has_pronunciation_analysis"] = True

    up.user_answers = json.dumps(grading_result)
    up.score = new_overall
    db.commit()

    # Clean up audio file now that analysis is done
    Path(audio_path).unlink(missing_ok=True)

    return {
        "pronunciation_band": new_pron_band,
        "old_pronunciation_band": old_pron_band,
        "azure_scores": er["pronunciation"]["azure_scores"],
        "pronunciation_words": pronunciation_words,
        "overall_band": new_overall,
        "old_overall_band": old_overall,
    }


@router.post("/submit-ai-speaking-full", dependencies=[Depends(quota("grade"))])
async def submit_ai_speaking_full(
    audio_part1: UploadFile = File(...),
    audio_part2: UploadFile = File(...),
    audio_part3: UploadFile = File(...),
    practice_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full speaking test: 3 separate audio files → Whisper each → concatenate → GPT-4o grade."""
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

    # Save all 3 audio files
    SPEAKING_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    parts_data = []
    for i, (audio_file, label) in enumerate([
        (audio_part1, "Part 1"), (audio_part2, "Part 2"), (audio_part3, "Part 3")
    ]):
        audio_bytes = await audio_file.read()
        if len(audio_bytes) < 5000:
            logger.warning(f"[Speaking Full] {label} audio too short: {len(audio_bytes)} bytes")
            raise HTTPException(422, f"{label} audio too short. Please record at least a few seconds for each part.")
        audio_path = str(SPEAKING_AUDIO_DIR / f"{current_user.id}_{up.id}_part{i+1}.webm")
        Path(audio_path).write_bytes(audio_bytes)
        parts_data.append({"label": label, "path": audio_path, "size": len(audio_bytes)})
        logger.info(f"[Speaking Full] {label} saved: {len(audio_bytes)} bytes ({len(audio_bytes)/1024:.0f}KB)")

    # Step 1: Whisper transcription for all 3 parts (sequential to avoid rate limits)
    client = get_client()
    transcripts = []
    for part in parts_data:
        try:
            logger.info(f"[Speaking Full] Whisper: {part['label']}")
            with open(part["path"], "rb") as f:
                result = client.audio.transcriptions.create(model=settings.OPENAI_MODEL_TRANSCRIBE, file=f, response_format="text")
            text = result.strip() if isinstance(result, str) else result.text.strip()
            transcripts.append(f"[{part['label']}]\n{text}")
            logger.info(f"[Speaking Full] Whisper {part['label']} OK: {len(text)} chars")
        except Exception as e:
            logger.error(f"[Speaking Full] Whisper {part['label']} FAILED: {e}")
            transcripts.append(f"[{part['label']}]\n(transcription failed)")

    full_transcript = "\n\n".join(transcripts)
    logger.info(f"[Speaking Full] Combined transcript: {len(full_transcript)} chars")

    if len(full_transcript.replace("[Part 1]", "").replace("[Part 2]", "").replace("[Part 3]", "").strip()) < 20:
        for part in parts_data:
            Path(part["path"]).unlink(missing_ok=True)
        raise HTTPException(422, "No speech detected in any part. Please speak clearly and try again.")

    # Build context for grader — include all part details
    cue_card = {}
    part1_topics = content.get("part1", {}).get("topics", [])
    part2_cue = content.get("part2", {}).get("cue_card", {})
    part3_topics = content.get("part3", {}).get("topics", [])

    # Build comprehensive context for GPT
    context_parts = []
    if part1_topics:
        p1_qs = []
        for t in part1_topics:
            p1_qs.extend(t.get("questions", []))
        context_parts.append(f"Part 1 questions: {'; '.join(p1_qs)}")
    if part2_cue:
        context_parts.append(f"Part 2 cue card: {part2_cue.get('topic_line', '')} — {', '.join(part2_cue.get('bullets', []))}")
    if part3_topics:
        p3_qs = []
        for t in part3_topics:
            p3_qs.extend(t.get("questions", []))
        context_parts.append(f"Part 3 discussion questions: {'; '.join(p3_qs)}")

    cue_card = {"topic_line": "Full IELTS Speaking Test (Parts 1, 2, and 3)", "bullets": context_parts}

    # Step 2: GPT-4o grading
    try:
        logger.info(f"[Speaking Full] GPT-4o grading, transcript={len(full_transcript)} chars")
        grader = SpeakingGrader()
        grading_result = grader.grade(full_transcript, cue_card, azure_scores=None)
        logger.info(f"[Speaking Full] GPT-4o OK: overall_band={grading_result.get('examiner_result', {}).get('overall_band', '?')}")
    except Exception as e:
        logger.error(f"[Speaking Full] GPT-4o grading FAILED: {e}", exc_info=True)
        for part in parts_data:
            Path(part["path"]).unlink(missing_ok=True)
        raise HTTPException(500, "Grading failed. Please try again.")

    # Store results
    overall = grading_result.get("examiner_result", {}).get("overall_band", 0)
    grading_result["transcript"] = full_transcript
    grading_result["has_pronunciation_analysis"] = False
    grading_result["audio_paths"] = [p["path"] for p in parts_data]

    up.submitted_at = datetime.utcnow()
    up.user_answers = json.dumps(grading_result)
    up.score = overall
    db.commit()

    return grading_result
