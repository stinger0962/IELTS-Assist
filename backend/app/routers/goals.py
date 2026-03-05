from datetime import datetime, date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.models import Goal, StudySession, UserPractice, User
from app.schemas.schemas import GoalCreate, GoalResponse, GoalTodayProgressItem, GoalUpdate
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
        target_minutes=goal.target_minutes,
        skill=goal.skill,
        goal_type=goal.goal_type,
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


@router.get("/today-progress", response_model=List[GoalTodayProgressItem])
def get_today_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return today's actual vs target for each active templated goal."""
    active_goals = (
        db.query(Goal)
        .filter(
            Goal.user_id == current_user.id,
            Goal.completed == False,
            Goal.goal_type.isnot(None),
            Goal.skill.isnot(None),
        )
        .all()
    )

    today_start = datetime.combine(date.today(), datetime.min.time())
    week_start = datetime.combine(date.today() - timedelta(days=date.today().weekday()), datetime.min.time())

    result = []
    for goal in active_goals:
        target = goal.target_minutes or 0
        actual = 0

        if goal.goal_type == "daily_minutes":
            row = (
                db.query(func.sum(StudySession.duration_minutes))
                .filter(
                    StudySession.user_id == current_user.id,
                    StudySession.skill == goal.skill,
                    StudySession.created_at >= today_start,
                )
                .scalar()
            )
            actual = row or 0

        elif goal.goal_type == "weekly_exercises":
            target = goal.target_minutes or 5  # reuse target_minutes as weekly count target
            row = (
                db.query(func.count(UserPractice.id))
                .filter(
                    UserPractice.user_id == current_user.id,
                    UserPractice.submitted_at.isnot(None),
                    UserPractice.submitted_at >= week_start,
                )
                .scalar()
            )
            actual = row or 0

        result.append(GoalTodayProgressItem(
            goal_id=goal.id,
            title=goal.title,
            skill=goal.skill,
            goal_type=goal.goal_type,
            target=target,
            actual=actual,
        ))

    return result
