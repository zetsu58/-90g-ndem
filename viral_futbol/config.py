from __future__ import annotations

import os
from dataclasses import dataclass, field

# X is a general Turkish breaking-news desk, not a football-only feed.
DEFAULT_X_QUERIES = (
    "Türkiye son dakika",
    "Türkiye gündem",
    "siyaset son dakika",
    "ekonomi son dakika",
    "gündelik yaşam son dakika",
    "dünya son dakika",
    "teknoloji son dakika",
    "sağlık son dakika",
)

# Shorts remains strictly football.
DEFAULT_QUERIES = (
    "Galatasaray transfer", "Fenerbahçe transfer", "Beşiktaş transfer",
    "Trabzonspor transfer", "Türkiye futbol son dakika",
)
DEFAULT_GLOBAL_QUERIES = (
    "football breaking news", "football transfer news", "Premier League latest news",
    "Champions League latest news", "Real Madrid Barcelona latest news",
)

def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(x.strip() for x in raw.split(",") if x.strip()) or default

def _languages() -> tuple[str, ...]:
    requested = _csv("NEWS_LANGUAGES", ("tr", "en"))
    supported = tuple(dict.fromkeys(x.casefold() for x in requested if x.casefold() in {"tr", "en"}))
    return supported or ("tr",)

@dataclass(frozen=True)
class Settings:
    mpt_url: str = os.getenv("MPT_API_URL", "http://127.0.0.1:8080/api/v1")
    mpt_api_key: str = os.getenv("MPT_API_KEY", "")
    video_engine: str = os.getenv("VIDEO_ENGINE", "lite").strip().casefold()
    lite_video_dir: str = os.getenv("LITE_VIDEO_DIR", "storage/videos")
    x_queries: tuple[str, ...] = field(default_factory=lambda: _csv("X_NEWS_QUERIES", DEFAULT_X_QUERIES))
    queries: tuple[str, ...] = field(default_factory=lambda: _csv("NEWS_QUERIES", DEFAULT_QUERIES))
    global_queries: tuple[str, ...] = field(default_factory=lambda: _csv("NEWS_GLOBAL_QUERIES", DEFAULT_GLOBAL_QUERIES))
    languages: tuple[str, ...] = field(default_factory=_languages)
    poll_seconds: int = int(os.getenv("NEWS_POLL_SECONDS", "120"))
    x_max_age_minutes: int = int(os.getenv("X_NEWS_MAX_AGE_MINUTES", "3"))
    shorts_max_age_minutes: int = int(os.getenv("SHORTS_MAX_AGE_MINUTES", "7"))
    max_age_minutes: int = int(os.getenv("NEWS_MAX_AGE_MINUTES", "7"))
    min_sources: int = int(os.getenv("NEWS_MIN_SOURCES", "2"))
    similarity: float = float(os.getenv("NEWS_TITLE_SIMILARITY", "0.52"))
    dry_run: bool = os.getenv("NEWS_DRY_RUN", "true").lower() in {"1", "true", "yes"}
    db_path: str = os.getenv("NEWS_DB_PATH", "storage/viral_futbol.sqlite3")
    voice_name: str = os.getenv("NEWS_VOICE", "tr-TR-EmelNeural")
    english_voice_name: str = os.getenv("NEWS_EN_VOICE", "en-US-GuyNeural-Male")
    video_source: str = os.getenv("NEWS_VIDEO_SOURCE", "pexels")
    video_clip_duration: int = int(os.getenv("NEWS_VIDEO_CLIP_DURATION", "5"))
    voice_rate: float = float(os.getenv("NEWS_VOICE_RATE", "1.03"))
    bgm_type: str = os.getenv("NEWS_BGM_TYPE", "").strip()
    bgm_volume: float = float(os.getenv("NEWS_BGM_VOLUME", "0.10"))
    fetch_workers: int = int(os.getenv("NEWS_FETCH_WORKERS", "5"))
    max_inflight_tasks: int = int(os.getenv("NEWS_MAX_INFLIGHT_TASKS", "2"))
    max_task_attempts: int = int(os.getenv("NEWS_MAX_TASK_ATTEMPTS", "3"))
    retry_delay_seconds: int = int(os.getenv("NEWS_RETRY_DELAY_SECONDS", "300"))
    submission_stale_seconds: int = int(os.getenv("NEWS_SUBMISSION_STALE_SECONDS", "300"))
    mpt_request_timeout: int = int(os.getenv("MPT_REQUEST_TIMEOUT", "30"))
