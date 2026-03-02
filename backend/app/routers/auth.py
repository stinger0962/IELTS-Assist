from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models.models import User, UserProgress, SkillType
from app.schemas.schemas import (
    UserCreate, UserLogin, Token, UserResponse,
    UserProgressResponse, ProgressStats, UserProgressUpdate,
    StudySessionCreate, StudySessionResponse,
    MistakeCreate, MistakeResponse, MistakeUpdate,
    PracticeResultCreate, PracticeResultResponse,
    TopicResponse, FlashCardResponse, TopicReviewCreate,
    GoalCreate, GoalResponse, GoalUpdate,
    SettingsUpdate
)
from app.services.auth import get_password_hash, authenticate_user, create_access_token, get_current_user
from app.config import settings

router = APIRouter()

# Auth Endpoints
@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(
        (User.email == user.email) | (User.username == user.username)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email or username already exists")
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create initial progress for all skills
    for skill in SkillType:
        progress = UserProgress(user_id=db_user.id, skill=skill)
        db.add(progress)
    db.commit()
    
    return db_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/settings", response_model=UserResponse)
def update_settings(
    settings_update: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if settings_update.target_band is not None:
        current_user.target_band = settings_update.target_band
    if settings_update.test_date is not None:
        current_user.test_date = settings_update.test_date
    if settings_update.preferred_language is not None:
        current_user.preferred_language = settings_update.preferred_language
    db.commit()
    db.refresh(current_user)
    return current_user