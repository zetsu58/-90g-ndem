from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timezone

from .performance_learning import PerformanceSample, PerformanceStore
from .youtube_publisher import YouTubeConfig
from .scene_performance import record_story_scene_snapshot
from .retention_collector import collect_video_retention


def _youtube(config: YouTubeConfig):
    from googleapiclient.discovery import build

    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if api_key:
        return build("youtube", "v3", developerKey=api_key, cache_discovery=False)

    from google.oauth2.credentials import Credentials
    credentials = Credentials(
        token=None,
        refresh_token=config.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config.client_id,
        client_secret=config.client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.readonly"],
    )
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def _published(db_path: str, limit: int) -> list[dict]:
    db = sqlite3.connect(db_path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        columns = {row[1] for row in db.execute("PRAGMA table_info(youtube_publications)").fetchall()}
        if "published_at" not in columns:
            db.execute("ALTER TABLE youtube_publications ADD COLUMN published_at REAL")
            db.commit()
        rows = db.execute(
            """
            SELECT p.story_id, p.video_id, p.updated_at, p.published_at
            FROM youtube_publications p
            WHERE p.status='published' AND p.video_id IS NOT NULL
            ORDER BY p.updated_at DESC LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        db.close()


def _chunks(items: list[dict], size: int = 50):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def collect_youtube_performance(db_path: str, limit: int | None = None) -> dict:
    config = YouTubeConfig.from_env()
    api_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    analytics_ready = bool(api_key) or config.ready
    result = {"enabled": config.enabled, "ready": analytics_ready, "auth_mode": "api_key" if api_key else "oauth", "checked": 0, "recorded": 0, "missing": 0}
    if not analytics_ready:
        return result

    try:
        analytics_limit = int(os.getenv("YOUTUBE_ANALYTICS_LIMIT", "100"))
    except ValueError:
        analytics_limit = 100
    jobs = _published(db_path, limit or analytics_limit)
    if not jobs:
        return result

    by_video = {str(job["video_id"]): job for job in jobs}
    youtube = _youtube(config)
    with PerformanceStore(db_path) as performance:
        for batch in _chunks(jobs):
            ids = ",".join(str(job["video_id"]) for job in batch)
            response = youtube.videos().list(part="statistics,snippet", id=ids, maxResults=50).execute()
            seen = set()
            for item in response.get("items", []):
                video_id = str(item.get("id") or "")
                job = by_video.get(video_id)
                if not job:
                    continue
                seen.add(video_id)
                stats = item.get("statistics") or {}
                snippet = item.get("snippet") or {}
                published_at = snippet.get("publishedAt")
                try:
                    published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
                    age_hours = max(1.0, (datetime.now(timezone.utc) - published).total_seconds() / 3600.0)
                except (TypeError, ValueError):
                    age_hours = max(1.0, (time.time() - float(job["updated_at"])) / 3600.0)
                sample = PerformanceSample(
                    story_id=str(job["story_id"]),
                    views=int(stats.get("viewCount") or 0),
                    likes=int(stats.get("likeCount") or 0),
                    comments=int(stats.get("commentCount") or 0),
                    age_hours=age_hours,
                )
                score = performance.record(sample)
                from production.growth_report import record_snapshot
                record_snapshot(db_path, sample.story_id, lane='football_news', sample=sample)
                try:
                    record_story_scene_snapshot(
                        db_path, sample.story_id, age_hours=sample.age_hours,
                        views=sample.views, likes=sample.likes, comments=sample.comments,
                        performance_score=score,
                    )
                except Exception:
                    # Advisory learning must never block primary analytics collection.
                    pass
                if published_at:
                    try:
                        published_epoch = published.timestamp()
                        db = sqlite3.connect(db_path, timeout=30)
                        with db:
                            db.execute("UPDATE youtube_publications SET published_at=? WHERE story_id=?", (published_epoch, str(job["story_id"])))
                        db.close()
                    except Exception:
                        pass
                if config.ready:
                    try:
                        collect_video_retention(db_path,story_id=sample.story_id,video_id=video_id,
                            client_id=config.client_id,client_secret=config.client_secret,
                            refresh_token=config.refresh_token,
                            published_at=published.timestamp() if published_at else None)
                    except Exception:
                        # Analytics retention can be unavailable or delayed; never block base metrics.
                        pass
                result["recorded"] += 1
            result["checked"] += len(batch)
            result["missing"] += len(batch) - len(seen)
        result["leaders"] = performance.leaders(5)
    return result
