from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Boolean, ForeignKey, Text, Enum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class SkillType(str, enum.Enum):
    READING = "reading"
    LISTENING = "listening"
    WRITING = "writing"
    SPEAKING = "speaking"
    GRAMMAR = "grammar"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200))
    target_band = Column(Float, default=7.0)
    test_date = Column(DateTime, nullable=True)
    preferred_language = Column(String(10), default="en")
    role = Column(String(20), default="free")  # "free" or "vip"
    # Stamped on every password change. Access tokens issued before this moment
    # are rejected, so a reset ends sessions an attacker may already hold.
    password_changed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    progress = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("StudySession", back_populates="user", cascade="all, delete-orphan")
    mistakes = relationship("Mistake", back_populates="user", cascade="all, delete-orphan")
    practice_results = relationship("PracticeResult", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    user_practices = relationship("UserPractice", back_populates="user", cascade="all, delete-orphan")

class UserProgress(Base):
    __tablename__ = "user_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill = Column(Enum(SkillType), nullable=False)
    band_score = Column(Float, default=0.0)
    total_exercises = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    study_time_minutes = Column(Integer, default=0)
    last_practiced = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    user = relationship("User", back_populates="progress")

class StudySession(Base):
    __tablename__ = "study_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill = Column(Enum(SkillType), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)
    completed = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="sessions")

class Mistake(Base):
    __tablename__ = "mistakes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill = Column(Enum(SkillType), nullable=False)
    question = Column(Text, nullable=False)
    user_answer = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=False)
    mistake_type = Column(String(100), nullable=True)  # grammar, vocabulary, comprehension, etc.
    explanation = Column(Text, nullable=True)
    times_repeated = Column(Integer, default=1)
    last_reviewed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="mistakes")

class PracticeResult(Base):
    __tablename__ = "practice_results"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill = Column(Enum(SkillType), nullable=False)
    exercise_id = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    total_questions = Column(Integer, nullable=False)
    correct_answers = Column(Integer, nullable=False)
    time_taken_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="practice_results")

class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # NULL = global/curated
    skill = Column(Enum(SkillType), nullable=False)
    category = Column(String(100), nullable=False)  # vocabulary, grammar, topic_idea, etc.
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_zh = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    example_zh = Column(Text, nullable=True)
    difficulty = Column(Integer, default=1)  # 1-5
    phonetic = Column(String(100), nullable=True)   # IPA string, e.g. /ˈæmplɪfaɪ/
    audio_url = Column(String(500), nullable=True)  # self-hosted MP3 under TTS_AUDIO_URL_PREFIX
    created_at = Column(DateTime, server_default=func.now())


class VocabCache(Base):
    """One row per English word, shared by all users.

    Definitions are not user-specific, so caching globally means a word is
    generated once for the entire user base. IELTS vocabulary repeats heavily,
    so the hit rate is high and the marginal cost of a lookup trends to zero.
    """

    __tablename__ = "vocab_cache"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String(100), nullable=False, unique=True, index=True)  # lowercased
    definition_en = Column(Text, nullable=False)
    definition_zh = Column(Text, nullable=True)
    example = Column(Text, nullable=True)
    phonetic = Column(String(100), nullable=True)   # IPA, e.g. /ˈæmplɪfaɪ/
    audio_url = Column(String(500), nullable=True)  # self-hosted, under TTS_AUDIO_URL_PREFIX
    created_at = Column(DateTime, server_default=func.now())


class PasswordResetToken(Base):
    """Single-use, time-limited password reset token.

    Only the SHA-256 hash is stored: the value that can actually reset an
    account exists solely in the email that was sent, so a database leak
    yields nothing an attacker can use.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UsageCounter(Base):
    """Paid-AI usage per user, per UTC day, per category.

    Database-backed rather than in-process: deploys restart the app several
    times a day and would otherwise reset everyone's quota.
    """

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("user_id", "day", "category", name="uq_usage_user_day_category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    day = Column(Date, nullable=False, index=True)   # UTC
    category = Column(String(20), nullable=False)    # grade | generate | lookup
    count = Column(Integer, nullable=False, default=0)


class TopicReview(Base):
    __tablename__ = "topic_reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    next_review = Column(DateTime, nullable=True)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    repetitions = Column(Integer, default=0)
    last_reviewed = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

class Goal(Base):
    __tablename__ = "goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_date = Column(DateTime, nullable=True)
    target_minutes = Column(Integer, nullable=True)
    skill = Column(String(50), nullable=True)          # reading|listening|writing|speaking
    goal_type = Column(String(50), default="daily_minutes")  # daily_minutes|weekly_exercises
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="goals")

class GeneratedPractice(Base):
    __tablename__ = "generated_practices"

    id = Column(Integer, primary_key=True, index=True)
    skill = Column(String(50), nullable=False)  # reading, listening, etc.
    topic = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)  # JSON content of the practice
    is_validated = Column(Boolean, default=False)
    generated_date = Column(DateTime, server_default=func.now())
    used_date = Column(DateTime, nullable=True)  # deprecated — kept for backwards compat

    user_practices = relationship("UserPractice", back_populates="practice")


class UserPractice(Base):
    """Per-user tracking of which exercises have been dealt and submitted."""
    __tablename__ = "user_practices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    practice_id = Column(Integer, ForeignKey("generated_practices.id"), nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())       # when card was dealt
    submitted_at = Column(DateTime, nullable=True)                 # null = active card
    user_answers = Column(Text, nullable=True)                     # JSON — future Mistakes area
    score = Column(Float, nullable=True)
    correct_count = Column(Integer, nullable=True)
    total_questions = Column(Integer, nullable=True)

    user = relationship("User", back_populates="user_practices")
    practice = relationship("GeneratedPractice", back_populates="user_practices")


class StudyPassGrant(Base):
    """Internal grants only. No endpoint can mint one; payment integration is separate."""
    __tablename__ = "study_pass_grants"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    source_key = Column(String(200), nullable=False, unique=True)
    kind = Column(String(20), nullable=False)  # pass | trial
    starts_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    reviews_granted = Column(Integer, nullable=False)
    reviews_remaining = Column(Integer, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class WritingReviewReservation(Base):
    __tablename__ = "writing_review_reservations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    user_practice_id = Column(Integer, ForeignKey("user_practices.id"), nullable=False, unique=True)
    grant_id = Column(Integer, ForeignKey("study_pass_grants.id"), nullable=True)
    token = Column(String(36), nullable=False)
    state = Column(String(20), nullable=False)  # pending | completed | released
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class CheckoutOrder(Base):
    """Offline/test-provider foundation only; offers are immutable server snapshots."""
    __tablename__ = "checkout_orders"

    id = Column(String(36), primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # Nullable unique slot prevents concurrent unresolved or active purchases.
    active_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    idempotency_key = Column(String(100), nullable=False)
    provider = Column(String(50), nullable=False)
    provider_account_id = Column(String(100), nullable=False)
    mode = Column(String(10), nullable=False)
    sku = Column(String(100), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    reviews = Column(Integer, nullable=False)
    duration_days = Column(Integer, nullable=False)
    state = Column(String(20), nullable=False)  # pending | fulfilled | refunded | review
    session_id = Column(String(200), nullable=True)
    payment_id = Column(String(200), nullable=True)
    checkout_url = Column(Text, nullable=True)
    grant_id = Column(Integer, ForeignKey("study_pass_grants.id"), nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False)
    fulfilled_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key"),
        UniqueConstraint("provider", "provider_account_id", "mode", "session_id"),
        UniqueConstraint("provider", "provider_account_id", "mode", "payment_id"),
    )


class CheckoutEvent(Base):
    __tablename__ = "checkout_events"

    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)
    provider_account_id = Column(String(100), nullable=False)
    mode = Column(String(10), nullable=False)
    event_id = Column(String(200), nullable=False)
    order_id = Column(String(36), ForeignKey("checkout_orders.id"), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    outcome = Column(String(20), nullable=False)
    processed_at = Column(DateTime, nullable=False)
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id", "mode", "event_id"),
    )
