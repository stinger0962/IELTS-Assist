import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import User, UserProgress, UserPractice, GeneratedPractice, StudySession, SkillType

logger = logging.getLogger(__name__)
from app.schemas.schemas import (
    UserProgressResponse, ProgressStats, UserProgressUpdate,
    StudySessionCreate, StudySessionResponse
)
from app.services.auth import get_current_user

router = APIRouter()

@router.get("/progress", response_model=List[UserProgressResponse])
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(UserProgress).filter(UserProgress.user_id == current_user.id).all()

@router.post("/progress", response_model=UserProgressResponse)
def update_progress(
    progress_update: UserProgressUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    progress = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id,
        UserProgress.skill == progress_update.skill
    ).first()
    
    if not progress:
        progress = UserProgress(
            user_id=current_user.id,
            skill=progress_update.skill,
            band_score=progress_update.band_score or 0,
            total_exercises=progress_update.total_questions or 0,
            correct_answers=progress_update.correct_answers or 0,
            study_time_minutes=progress_update.study_time_minutes or 0
        )
        db.add(progress)
    else:
        if progress_update.band_score is not None:
            progress.band_score = progress_update.band_score
        if progress_update.total_questions is not None:
            progress.total_exercises += progress_update.total_questions
        if progress_update.correct_answers is not None:
            progress.correct_answers += progress_update.correct_answers
        if progress_update.study_time_minutes is not None:
            progress.study_time_minutes += progress_update.study_time_minutes
        progress.last_practiced = datetime.utcnow()
    
    db.commit()
    db.refresh(progress)
    return progress

@router.get("/progress/stats", response_model=ProgressStats)
def get_progress_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    progress_list = db.query(UserProgress).filter(
        UserProgress.user_id == current_user.id
    ).all()
    
    total_time = sum(p.study_time_minutes for p in progress_list)
    total_exercises = sum(p.total_exercises for p in progress_list)
    band_scores = [p.band_score for p in progress_list if p.band_score > 0]
    avg_band = sum(band_scores) / len(band_scores) if band_scores else 0.0
    
    # Calculate streak
    sessions = db.query(StudySession).filter(
        StudySession.user_id == current_user.id,
        StudySession.completed == True
    ).order_by(StudySession.created_at.desc()).all()
    
    streak_days = 0
    if sessions:
        today = datetime.utcnow().date()
        current_date = today
        session_dates = {s.created_at.date() for s in sessions}
        
        while current_date in session_dates:
            streak_days += 1
            current_date -= timedelta(days=1)
    
    return ProgressStats(
        total_study_time=total_time,
        total_exercises=total_exercises,
        average_band=round(avg_band, 1),
        streak_days=streak_days,
        progress=progress_list
    )

@router.post("/sessions", response_model=StudySessionResponse)
def create_session(
    session: StudySessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_session = StudySession(
        user_id=current_user.id,
        skill=session.skill,
        duration_minutes=session.duration_minutes,
        notes=session.notes
    )
    db.add(db_session)
    db.commit()
    db.refresh(db_session)
    return db_session

@router.get("/sessions", response_model=List[StudySessionResponse])
def get_sessions(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(StudySession).filter(
        StudySession.user_id == current_user.id
    ).order_by(StudySession.created_at.desc()).limit(limit).all()


# ── Speaking insights ────────────────────────────────────────────────────────

CRITERION_KEYS = [
    ("fluency_coherence", "Fluency & Coherence"),
    ("lexical_resource", "Lexical Resource"),
    ("grammatical_range_accuracy", "Grammar Range & Accuracy"),
    ("pronunciation", "Pronunciation"),
]

WEAKNESS_RECOMMENDATIONS = {
    "fluency_coherence": "Practice speaking at length without pauses. Use discourse markers naturally.",
    "lexical_resource": "Build topic-specific vocabulary. Use paraphrase instead of repetition.",
    "grammatical_range_accuracy": "Focus on complex sentence structures. Reduce recurring grammar errors.",
    "pronunciation": "Practice mispronounced words. Use the pronunciation analysis for targeted feedback.",
}


@router.get("/progress/speaking-insights")
def get_speaking_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate speaking criterion data across all submitted sessions."""
    rows = (
        db.query(UserPractice, GeneratedPractice)
        .join(GeneratedPractice, UserPractice.practice_id == GeneratedPractice.id)
        .filter(
            UserPractice.user_id == current_user.id,
            GeneratedPractice.skill == "speaking",
            UserPractice.submitted_at.isnot(None),
        )
        .order_by(UserPractice.submitted_at.desc())
        .all()
    )

    # Parse criterion bands from each session
    sessions = []
    for up, gp in rows:
        try:
            data = json.loads(up.user_answers) if up.user_answers else {}
            er = data.get("examiner_result", {})
            bands = {}
            for key, _ in CRITERION_KEYS:
                b = er.get(key, {}).get("band")
                if b is not None:
                    bands[key] = float(b)
            if bands and er.get("overall_band") is not None:
                sessions.append({
                    "bands": bands,
                    "overall": float(er["overall_band"]),
                    "date": up.submitted_at.isoformat() if up.submitted_at else None,
                    "topic": gp.topic,
                })
        except Exception:
            continue

    total = len(sessions)
    if total == 0:
        return {
            "total_sessions": 0,
            "criteria": [],
            "weakest_criterion": None,
            "weakest_recommendation": None,
            "best_session_band": None,
            "worst_session_band": None,
            "overall_average": None,
            "recent_sessions": [],
        }

    # Per-criterion averages
    criteria = []
    weakest_key = None
    weakest_avg = 10.0
    for key, label in CRITERION_KEYS:
        all_bands = [s["bands"][key] for s in sessions if key in s["bands"]]
        if not all_bands:
            criteria.append({"name": key, "label": label, "average": 0, "trend": "insufficient"})
            continue

        avg = round(sum(all_bands) / len(all_bands) * 2) / 2  # nearest 0.5

        # Trend: last 3 vs previous 3
        if total >= 6:
            recent_3 = [s["bands"][key] for s in sessions[:3] if key in s["bands"]]
            prev_3 = [s["bands"][key] for s in sessions[3:6] if key in s["bands"]]
            if recent_3 and prev_3:
                delta = (sum(recent_3) / len(recent_3)) - (sum(prev_3) / len(prev_3))
                trend = "improving" if delta > 0.25 else "declining" if delta < -0.25 else "stable"
            else:
                trend = "insufficient"
        else:
            trend = "insufficient"

        criteria.append({"name": key, "label": label, "average": avg, "trend": trend})

        if avg < weakest_avg:
            weakest_avg = avg
            weakest_key = key

    # Overall stats
    overall_bands = [s["overall"] for s in sessions]
    overall_avg = round(sum(overall_bands) / len(overall_bands) * 2) / 2

    # Recent sessions (last 5)
    recent = [
        {"date": s["date"], "overall_band": s["overall"], "topic": s["topic"]}
        for s in sessions[:5]
    ]

    weakest_label = None
    for key, label in CRITERION_KEYS:
        if key == weakest_key:
            weakest_label = label
            break

    return {
        "total_sessions": total,
        "criteria": criteria,
        "weakest_criterion": weakest_label,
        "weakest_recommendation": WEAKNESS_RECOMMENDATIONS.get(weakest_key) if weakest_key else None,
        "best_session_band": max(overall_bands),
        "worst_session_band": min(overall_bands),
        "overall_average": overall_avg,
        "recent_sessions": recent,
    }