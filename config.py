"""Central configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")

REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "YoutubeShorts/1.0")

PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY: str = os.getenv("PIXABAY_API_KEY", "")

YOUTUBE_CLIENT_SECRETS_FILE: str = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
YOUTUBE_TOKEN_FILE: str = os.getenv("YOUTUBE_TOKEN_FILE", "token.json")

# ── Bot Settings ──────────────────────────────────────────────────────────────
SHORTS_PER_RUN: int = int(os.getenv("SHORTS_PER_RUN", "3"))
TARGET_NICHE: str = os.getenv("TARGET_NICHE", "")
VOICE_PROVIDER: str = os.getenv("VOICE_PROVIDER", "gtts")
TTS_LANGUAGE: str = os.getenv("TTS_LANGUAGE", "en")
AUTO_UPLOAD: bool = os.getenv("AUTO_UPLOAD", "true").lower() == "true"
CRON_SCHEDULE: str = os.getenv("CRON_SCHEDULE", "")

# ── Video Settings ─────────────────────────────────────────────────────────────
VIDEO_WIDTH: int = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT: int = int(os.getenv("VIDEO_HEIGHT", "1920"))
MAX_CLIP_DURATION: int = int(os.getenv("MAX_CLIP_DURATION", "59"))
MUSIC_VOLUME: float = float(os.getenv("MUSIC_VOLUME", "0.15"))
WATERMARK_TEXT: str = os.getenv("WATERMARK_TEXT", "")

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
DOWNLOADS_DIR = BASE_DIR / os.getenv("DOWNLOADS_DIR", "output/downloads")
EDITED_DIR = BASE_DIR / os.getenv("EDITED_DIR", "output/edited")
FINAL_DIR = BASE_DIR / os.getenv("FINAL_DIR", "output/final")
ASSETS_DIR = BASE_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"

# ── Claude Model ──────────────────────────────────────────────────────────────
CLAUDE_MODEL: str = "claude-sonnet-4-6"

# ── YouTube Upload Defaults ────────────────────────────────────────────────────
YOUTUBE_CATEGORY_ID: str = "22"       # People & Blogs (common for Shorts)
YOUTUBE_DEFAULT_PRIVACY: str = "public"

def validate() -> None:
    """Raise if critical keys are missing."""
    if not ANTHROPIC_API_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set in .env")
