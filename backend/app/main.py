from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import init_db
from app.routers import auth, progress, practice, mistakes, topics, goals

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="IELTS Preparation Assistant API"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
init_db()

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["Auth"])
app.include_router(progress.router, prefix=f"{settings.API_PREFIX}", tags=["Progress"])
app.include_router(practice.router, prefix=f"{settings.API_PREFIX}/practice", tags=["Practice"])
app.include_router(mistakes.router, prefix=f"{settings.API_PREFIX}/mistakes", tags=["Mistakes"])
app.include_router(topics.router, prefix=f"{settings.API_PREFIX}/topics", tags=["Topics"])
app.include_router(goals.router, prefix=f"{settings.API_PREFIX}/goals", tags=["Goals"])

@app.get("/")
def root():
    return {"message": "IELTS Assist API", "version": settings.VERSION}

@app.get("/health")
def health_check():
    return {"status": "healthy"}