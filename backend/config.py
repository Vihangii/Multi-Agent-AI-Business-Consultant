import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Backend API Configuration
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))

# Upload limits
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

# CORS — comma-separated list of allowed origins, "*" for any (default, local dev)
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Placeholder value shipped in .env.example — treat it as "no key"
_PLACEHOLDER_PREFIX = "sk-your-"


def has_openai_key() -> bool:
    """Return True when a real (non-placeholder) OpenAI API key is configured."""
    return bool(OPENAI_API_KEY) and not OPENAI_API_KEY.startswith(_PLACEHOLDER_PREFIX)


def require_openai_key() -> str:
    """
    Return the configured OpenAI API key.

    Raises:
        ValueError: If no key is set. Called lazily by the recommendation agent
            so the backend can still start and run the data/forecast stages
            without a key (``skip_recommendations=True``).
    """
    if not has_openai_key():
        raise ValueError(
            "OPENAI_API_KEY not found. Set it in the .env file, "
            "or run with skip_recommendations=True."
        )
    return OPENAI_API_KEY

# Optional shared secret. When set, /analyze and /inspect require an
# X-API-Key header with this value. Leave unset for open local development.
API_KEY = os.getenv("API_KEY") or None

# Remote file ingestion. Vercel caps request bodies at 4.5 MB, so large files
# are uploaded to Vercel Blob by the browser and passed to the API as a URL.
# Only these hosts (exact or "*.suffix" wildcards) may be fetched — this keeps
# the function from acting as an open proxy. Comma-separated.
FILE_URL_ALLOWED_HOSTS = [
    h.strip().lower()
    for h in os.getenv("FILE_URL_ALLOWED_HOSTS", "*.public.blob.vercel-storage.com").split(",")
    if h.strip()
]

# True when running as a Vercel serverless function
IS_VERCEL = bool(os.getenv("VERCEL"))
