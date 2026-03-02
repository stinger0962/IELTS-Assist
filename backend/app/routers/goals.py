from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.models import User, Goal
from app.schemas.schemas import GoalCreate, GoalResponse, GoalUpdate
from app.services.auth import get_current_user

router = APIRouter()

@router.get("", response_model=List[GoalResponse])
def get_goals(
    completed: bool = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Goal).filter(Goal.user_id == current_user.id)
    if completed is not None:
        query = query.filter(Goal.completed == completed)
    return query.order_by(Goal.created_at.desc()).limit(limit).all()

@router.post("", response_model=GoalResponse)
def create_goal(
    goal: GoalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_goal = Goal(
        user_id=current_user.id,
        title=goal.title,
        description=goal.description,
        target_date=goal.target_date,
        target_minutes=goal.target_minutes
    )
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal

@router.put("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    update: GoalUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    if update.completed is not None:
        goal.completed = update.completed
    
    db.commit()
    db.refresh(goal)
    return goal

@router.delete("/{goal_id}")
def delete_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    goal = db.query(Goal).filter(
        Goal.id == goal_id,
        Goal.user_id == current_user.id
    ).first()
    
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    
    db.delete(goal)
    db.commit()
    return {"message": "Goal deleted successfully"}