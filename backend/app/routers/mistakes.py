from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from app.database import get_db
from app.models.models import User, Mistake, SkillType
from app.schemas.schemas import MistakeCreate, MistakeResponse, MistakeUpdate
from app.services.auth import get_current_user

router = APIRouter()

@router.get("", response_model=List[MistakeResponse])
def get_mistakes(
    skill: SkillType = None,
    mistake_type: str = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Mistake).filter(Mistake.user_id == current_user.id)
    if skill:
        query = query.filter(Mistake.skill == skill)
    if mistake_type:
        query = query.filter(Mistake.mistake_type == mistake_type)
    return query.order_by(Mistake.created_at.desc()).limit(limit).all()

@router.post("", response_model=MistakeResponse)
def create_mistake(
    mistake: MistakeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check for duplicate mistake
    existing = db.query(Mistake).filter(
        Mistake.user_id == current_user.id,
        Mistake.skill == mistake.skill,
        Mistake.question == mistake.question,
        Mistake.correct_answer == mistake.correct_answer
    ).first()
    
    if existing:
        existing.times_repeated += 1
        existing.last_reviewed = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    
    db_mistake = Mistake(
        user_id=current_user.id,
        skill=mistake.skill,
        question=mistake.question,
        user_answer=mistake.user_answer,
        correct_answer=mistake.correct_answer,
        mistake_type=mistake.mistake_type,
        explanation=mistake.explanation
    )
    db.add(db_mistake)
    db.commit()
    db.refresh(db_mistake)
    return db_mistake

@router.put("/{mistake_id}", response_model=MistakeResponse)
def update_mistake(
    mistake_id: int,
    update: MistakeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mistake = db.query(Mistake).filter(
        Mistake.id == mistake_id,
        Mistake.user_id == current_user.id
    ).first()
    
    if not mistake:
        raise HTTPException(status_code=404, detail="Mistake not found")
    
    if update.times_repeated is not None:
        mistake.times_repeated = update.times_repeated
    if update.last_reviewed is not None:
        mistake.last_reviewed = update.last_reviewed
    
    db.commit()
    db.refresh(mistake)
    return mistake

@router.delete("/{mistake_id}")
def delete_mistake(
    mistake_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mistake = db.query(Mistake).filter(
        Mistake.id == mistake_id,
        Mistake.user_id == current_user.id
    ).first()
    
    if not mistake:
        raise HTTPException(status_code=404, detail="Mistake not found")
    
    db.delete(mistake)
    db.commit()
    return {"message": "Mistake deleted successfully"}

@router.get("/stats")
def get_mistake_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mistakes = db.query(Mistake).filter(Mistake.user_id == current_user.id).all()
    
    by_skill = {}
    by_type = {}
    total_mistakes = len(mistakes)
    total_repeats = sum(m.times_repeated for m in mistakes)
    
    for m in mistakes:
        skill_name = m.skill.value
        by_skill[skill_name] = by_skill.get(skill_name, 0) + 1
        
        if m.mistake_type:
            by_type[m.mistake_type] = by_type.get(m.mistake_type, 0) + 1
    
    return {
        "total_mistakes": total_mistakes,
        "total_repeats": total_repeats,
        "by_skill": by_skill,
        "by_type": by_type
    }