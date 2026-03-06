import logging
import sys
import traceback
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Explicitly attach a stderr StreamHandler so logs are visible in journalctl
# regardless of whether uvicorn has already called logging.basicConfig().
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s'))
_root = logging.getLogger()
_root.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in _root.handlers):
    _root.addHandler(_handler)

logger = logging.getLogger(__name__)

from app.config import settings
from app.database import init_db
from app.routers import auth, generate, goals, mistakes, practice, progress, topics
from app.routers.generate import daily_generate


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(daily_generate, CronTrigger(hour=0, minute=0), id="daily_generate")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="IELTS Preparation Assistant API",
    lifespan=lifespan,
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
app.include_router(generate.router, prefix=f"{settings.API_PREFIX}/generate", tags=["Generate"])
app.include_router(goals.router, prefix=f"{settings.API_PREFIX}/goals", tags=["Goals"])

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    tb = traceback.format_exc()
    logger.error("Unhandled exception on %s %s\n%s", request.method, request.url.path, tb)
    # print() to stderr as a guaranteed fallback (visible in journalctl regardless of log config)
    print(f"[IELTS ERROR] {request.method} {request.url.path}\n{tb}", file=sys.stderr, flush=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
def root():
    return {"message": "IELTS Assist API", "version": settings.VERSION}

@app.get("/health")
def health_check():
    return {"status": "healthy"}