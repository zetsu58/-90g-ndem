from __future__ import annotations

import os
from dataclasses import dataclass, field


DEFAULT_QUERIES = (
    "Galatasaray transfer",
    "Fenerbahçe transfer",
    "Beşiktaş transfer",
    "Trabzonspor transfer",
    "Türkiye futbol son dakika",
)


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(x.strip() for x in raw.split(",") if x.strip()) or default


@dataclass(frozen=True)
class Settings:
    mpt_url: str = os.getenv("MPT_API_URL", "http://127.0.0.1:8080/api/v1")
    mpt_api_key: str = os.getenv("MPT_API_KEY", "")
    queries: tuple[str, ...] = field(default_factory=lambda: _csv("NEWS_QUERIES", DEFAULT_QUERIES))
    poll_seconds: int = int(os.getenv("NEWS_POLL_SECONDS", "300"))
    max_age_minutes: int = int(os.getenv("NEWS_MAX_AGE_MINUTES", "90"))
    min_sources: int = int(os.getenv("NEWS_MIN_SOURCES", "2"))
    similarity: float = float(os.getenv("NEWS_TITLE_SIMILARITY", "0.52"))
    dry_run: bool = os.getenv("NEWS_DRY_RUN", "true").lower() in {"1", "true", "yes"}
    db_path: str = os.getenv("NEWS_DB_PATH", "storage/viral_futbol.sqlite3")
    voice_name: str = os.getenv("NEWS_VOICE", "tr-TR-AhmetNeural-Male")
    video_source: str = os.getenv("NEWS_VIDEO_SOURCE", "pexels")

