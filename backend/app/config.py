from pydantic_settings import BaseSettings
from functools import lru_cache

INSECURE_SECRET_KEY = "your-secret-key-change-in-production"


def assert_secret_key_is_safe(key: str) -> None:
    """Refuse to run with a guessable JWT signing key.

    Every token is signed and verified with this value, so the placeholder
    default would let anyone mint a token for any account.
    """
    if not key or key == INSECURE_SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is unset or still the placeholder. Set it via "
            "/root/IELTS-Assist/backend/.env (written by the deploy workflow "
            "from GitHub Secrets)."
        )


class Settings(BaseSettings):
    PROJECT_NAME: str = "IELTS Assist API"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ielts_assist"
    
    # Auth
    SECRET_KEY: str = INSECURE_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS — production is same-origin behind nginx, so these matter only for
    # local dev today. Listed explicitly so an API subdomain later doesn't get
    # debugged from a stale localhost-only default.
    BACKEND_CORS_ORIGINS: list = [
        "https://annababy.cc",
        "https://www.annababy.cc",
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    # Model tiers — override per environment without touching code.
    # grader:    band scoring (quality-critical, per-user cost)
    # generator: content authoring (quality matters, cost amortised across users)
    # utility:   short mechanical calls (cheapest tier)
    OPENAI_MODEL_GRADER: str = "gpt-5.6-luna"
    OPENAI_MODEL_GENERATOR: str = "gpt-5.6-luna"
    OPENAI_MODEL_UTILITY: str = "gpt-5.4-nano"
    # Speech-to-text for Speaking practice. Left on whisper-1 deliberately:
    # gpt-4o-mini-transcribe is newer and ~half the price, but transcript accuracy
    # on accented non-native speech feeds directly into Speaking band scores, so it
    # needs a listening test before switching.
    OPENAI_MODEL_TRANSCRIBE: str = "whisper-1"

    # --- AI usage quotas (per user, per UTC day) ---
    # Sized to bound catastrophe, not to ration study: normal use never reaches
    # these, but a runaway loop is capped.
    QUOTA_GRADE_PER_DAY: int = 30        # ~$1.50/day worst case per user
    QUOTA_GENERATE_PER_DAY: int = 60
    QUOTA_LOOKUP_PER_DAY: int = 300      # cache hits are refunded, so this is generous
    # Global circuit breaker: estimated spend across ALL users in a UTC day.
    DAILY_SPEND_CAP_USD: float = 20.0
    QUOTAS_ENABLED: bool = True          # kill switch: env change, no redeploy

    # Azure Speech — pronunciation assessment
    AZURE_SPEECH_KEY: str = ""
    AZURE_SPEECH_REGION: str = ""

    # Google Cloud TTS — listening practice audio
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    TTS_AUDIO_DIR: str = "/var/www/ielts-assist/audio"
    TTS_AUDIO_URL_PREFIX: str = "/audio"
    
    class Config:
        env_file = ".env"
        # .env is also systemd's EnvironmentFile, so it legitimately carries
        # process-level variables this model does not declare (PYTHONUNBUFFERED,
        # and anything added later). Without this, pydantic rejects them and the
        # app cannot even import.
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
