from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum

class SkillType(str, Enum):
    READING = "reading"
    LISTENING = "listening"
    WRITING = "writing"
    SPEAKING = "speaking"

# Auth Schemas
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    target_band: float
    test_date: Optional[datetime]
    preferred_language: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Progress Schemas
class UserProgressResponse(BaseModel):
    id: int
    skill: SkillType
    band_score: float
    total_exercises: int
    correct_answers: int
    study_time_minutes: int
    last_practiced: Optional[datetime]
    
    class Config:
        from_attributes = True

class ProgressStats(BaseModel):
    total_study_time: int
    total_exercises: int
    average_band: float
    streak_days: int
    progress: List[UserProgressResponse]

class UserProgressUpdate(BaseModel):
    skill: SkillType
    band_score: Optional[float] = None
    correct_answers: Optional[int] = None
    total_questions: Optional[int] = None
    study_time_minutes: Optional[int] = None

# Session Schemas
class StudySessionCreate(BaseModel):
    skill: Optional[SkillType] = None
    duration_minutes: int
    notes: Optional[str] = None

class StudySessionResponse(BaseModel):
    id: int
    skill: Optional[SkillType]
    duration_minutes: int
    notes: Optional[str]
    completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# Mistake Schemas
class MistakeCreate(BaseModel):
    skill: SkillType
    question: str
    user_answer: str
    correct_answer: str
    mistake_type: Optional[str] = None
    explanation: Optional[str] = None

class MistakeResponse(BaseModel):
    id: int
    skill: SkillType
    question: str
    user_answer: str
    correct_answer: str
    mistake_type: Optional[str]
    explanation: Optional[str]
    times_repeated: int
    last_reviewed: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True

class MistakeUpdate(BaseModel):
    times_repeated: Optional[int] = None
    last_reviewed: Optional[datetime] = None

# Practice Result Schemas
class PracticeResultCreate(BaseModel):
    skill: SkillType
    exercise_id: str
    score: float
    total_questions: int
    correct_answers: int
    time_taken_seconds: Optional[int] = None

class PracticeResultResponse(BaseModel):
    id: int
    skill: SkillType
    exercise_id: str
    score: float
    total_questions: int
    correct_answers: int
    time_taken_seconds: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Topic Schemas
class TopicResponse(BaseModel):
    id: int
    skill: SkillType
    category: str
    title: str
    content: str
    content_zh: Optional[str]
    example: Optional[str]
    example_zh: Optional[str]
    difficulty: int
    
    class Config:
        from_attributes = True

class TopicReviewCreate(BaseModel):
    topic_id: int
    quality: int  # 0-5 for spaced repetition

class FlashCardResponse(BaseModel):
    topic: TopicResponse
    next_review: Optional[datetime]
    ease_factor: float
    interval_days: int
    repetitions: int

# Goal Schemas
class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_date: Optional[datetime] = None
    target_minutes: Optional[int] = None

class GoalResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    target_date: Optional[datetime]
    target_minutes: Optional[int]
    completed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class GoalUpdate(BaseModel):
    completed: Optional[bool] = None

# Settings Schemas
class SettingsUpdate(BaseModel):
    target_band: Optional[float] = None
    test_date: Optional[datetime] = None
    preferred_language: Optional[str] = None