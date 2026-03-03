from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional
import json

from app.database import get_db
from app.models.models import GeneratedPractice, User
from app.services.auth import get_current_user
from app.services.ai.practice_generator import practice_generator

router = APIRouter()

@router.post("/generate-reading")
def generate_reading_practice(
    count: int = 3,
    topic_hint: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate reading practice questions"""
    generated = []
    
    for i in range(count):
        practice = practice_generator.generate_practice(topic_hint)
        if practice:
            # Save to database
            db_practice = GeneratedPractice(
                skill="reading",
                topic=practice.get("meta", {}).get("topic", ""),
                content=json.dumps(practice),
                is_validated=True,
                generated_date=datetime.utcnow()
            )
            db.add(db_practice)
            generated.append(practice)
    
    db.commit()
    return {"generated": len(generated), "practices": generated}


@router.get("/daily-reading")
def get_daily_reading(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get today's reading practices"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    
    practices = db.query(GeneratedPractice).filter(
        GeneratedPractice.skill == "reading",
        GeneratedPractice.generated_date >= today_start,
        GeneratedPractice.used_date.is_(None)
    ).limit(3).all()
    
    if not practices:
        # Generate new ones
        return generate_reading_practice(count=3, db=db, current_user=current_user)
    
    return {"practices": [json.loads(p.content) for p in practices]}


@router.post("/generate-more")
def generate_more_practice(
    count: int = 1,
    topic_hint: str = "",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Generate more practice on demand"""
    generated = []
    
    for i in range(count):
        practice = practice_generator.generate_practice(topic_hint)
        if practice:
            db_practice = GeneratedPractice(
                skill="reading",
                topic=practice.get("meta", {}).get("topic", ""),
                content=json.dumps(practice),
                is_validated=True,
                generated_date=datetime.utcnow()
            )
            db.add(db_practice)
            generated.append(practice)
    
    db.commit()
    return {"generated": len(generated), "practices": generated}
