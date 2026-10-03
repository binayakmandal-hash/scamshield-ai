"""Central configuration for ScamShield AI.

Values come from environment variables (or a local .env file) so that
secrets never live in source code.
"""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # --- Open-weight AI -----------------------------------------------------
    # "ollama"  -> local inference with an open-weight model (default: Gemma 4)
    # "openai"  -> any OpenAI-compatible server hosting an open-weight model
    #              (Ollama, LM Studio, vLLM, llama.cpp server, OpenRouter, HF router ...)
    # "none"    -> built-in rule engine only
    AI_PROVIDER = os.getenv("AI_PROVIDER", "ollama").strip().lower()
    AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "180"))  # local models on a laptop can be slow

    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b").strip()

    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "").strip()

    # --- Gmail -------------------------------------------------------------
    # Download the OAuth client JSON from Google Cloud Console and save it as client_secret.json,
    # or put the client id/secret in .env.
    GOOGLE_CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", os.path.join(BASE_DIR, "client_secret.json"))
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    GMAIL_REDIRECT_URI = os.getenv("GMAIL_REDIRECT_URI", "http://127.0.0.1:5000/oauth2callback").strip()
    GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", os.path.join(BASE_DIR, "gmail_token.json"))
    GMAIL_SCAN_LIMIT = int(os.getenv("GMAIL_SCAN_LIMIT", "25"))

    # --- Deployment ----------------------------------------------------------
    # PUBLIC_MODE=true on a public website (e.g. Render): every visitor gets a
    # private session with their own Gmail sign-in, history and learning.
    PUBLIC_MODE = _bool("PUBLIC_MODE", False)
    TOKENS_DIR = os.getenv("TOKENS_DIR", os.path.join(BASE_DIR, "instance", "tokens"))
    SESSION_COOKIE_SECURE = PUBLIC_MODE
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 7  # one week
    # Per-visitor limit on AI calls in PUBLIC_MODE, so a public site can't exhaust your API quota.
    AI_REQUESTS_PER_HOUR = int(os.getenv("AI_REQUESTS_PER_HOUR", "60"))

    # --- Storage & privacy --------------------------------------------------
    DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(BASE_DIR, "database.db"))
    # Turn history off entirely with SAVE_HISTORY=false
    SAVE_HISTORY = _bool("SAVE_HISTORY", True)
    # Mask long digit runs (OTPs, phone/account numbers) and email usernames
    # before anything is written to the database.
    REDACT_STORED_MESSAGES = _bool("REDACT_STORED_MESSAGES", True)

    # --- Limits ---------------------------------------------------------------
    MAX_MESSAGE_CHARS = int(os.getenv("MAX_MESSAGE_CHARS", "8000"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB upload limit (Flask setting)
    ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
