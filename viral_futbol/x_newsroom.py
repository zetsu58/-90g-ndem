from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .config import Settings
from .service import Story, _fetch_queries, verified_clusters


def fetch_x_newsroom(settings: Settings) -> list[list[Story]]:
    """Fetch general Turkish breaking news independently from football Shorts."""
    stories = _fetch_queries(
        settings.x_queries,
        language="tr",
        country="TR",
        workers=settings.fetch_workers,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.x_max_age_minutes)
    fresh = [story for story in stories if story.published >= cutoff]

    # Reuse the multi-source verifier but with the X-specific freshness window.
    x_settings = _XVerificationSettings(settings)
    return verified_clusters(fresh, x_settings)


class _XVerificationSettings:
    def __init__(self, settings: Settings) -> None:
        self.max_age_minutes = settings.x_max_age_minutes
        self.similarity = settings.similarity
        self.min_sources = settings.min_sources
