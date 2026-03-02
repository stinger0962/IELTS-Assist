from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
from app.database import get_db
from app.models.models import User, UserProgress, StudySession, SkillType
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