from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
import os

# Use SQLite for development if DATABASE_URL is not set properly or PostgreSQL unavailable
# For production, set DATABASE_URL to your PostgreSQL connection string
db_url = os.environ.get("DATABASE_URL", settings.DATABASE_URL)

# Fallback to SQLite if PostgreSQL is not available
try:
    engine = create_engine(db_url, echo=False)
    # Test connection
    with engine.connect() as conn:
        pass
except Exception:
    # Use SQLite as fallback
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "ielts_assist.db")
    db_url = f"sqlite:///{sqlite_path}"
    engine = create_engine(db_url, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models.models import Base
    from sqlalchemy import text
    Base.metadata.create_all(bind=engine)
    # Inline migrations for columns added after initial schema creation
    migrations = [
        "ALTER TABLE goals ADD COLUMN skill VARCHAR(50)",
        "ALTER TABLE goals ADD COLUMN goal_type VARCHAR(50) DEFAULT 'daily_minutes'",
        "ALTER TABLE topics ADD COLUMN user_id INTEGER REFERENCES users(id)",
        # created_at was present in the ORM model but may be missing from older DB schemas
        "ALTER TABLE topics ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        "ALTER TABLE topics ADD COLUMN phonetic VARCHAR(100)",
        "ALTER TABLE topics ADD COLUMN audio_url VARCHAR(500)",
    ]
    with engine.connect() as conn:
        for stmt in migrations:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                conn.rollback()  # PostgreSQL aborts the whole txn on error; must rollback before next stmt