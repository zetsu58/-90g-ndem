from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PerformanceSample:
    story_id: str
    views: int
    likes: int = 0
    comments: int = 0
    age_hours: float = 24.0


def _engagement(sample: PerformanceSample) -> float:
    views = max(1, sample.views)
    return (sample.likes + sample.comments * 2.0) / views


def performance_score(sample: PerformanceSample) -> float:
    """Return a bounded 0-100 score without letting raw views dominate forever."""
    velocity = sample.views / max(1.0, sample.age_hours)
    velocity_score = min(65.0, math.log1p(max(0.0, velocity)) * 8.5)
    engagement_score = min(35.0, _engagement(sample) * 700.0)
    return round(max(0.0, min(100.0, velocity_score + engagement_score)), 2)


class PerformanceStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout = 30000")
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS shorts_performance (
                story_id TEXT PRIMARY KEY,
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                age_hours REAL NOT NULL DEFAULT 0,
                score REAL NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL
            )
            """
        )
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.db.close()

    def record(self, sample: PerformanceSample) -> float:
        score = performance_score(sample)
        with self.db:
            self.db.execute(
                """
                INSERT INTO shorts_performance
                    (story_id, views, likes, comments, age_hours, score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(story_id) DO UPDATE SET
                    views=excluded.views, likes=excluded.likes,
                    comments=excluded.comments, age_hours=excluded.age_hours,
                    score=excluded.score, updated_at=excluded.updated_at
                """,
                (sample.story_id, max(0, sample.views), max(0, sample.likes),
                 max(0, sample.comments), max(0.0, sample.age_hours), score, time.time()),
            )
        return score

    def topic_boost(self, story_ids: list[str]) -> float:
        if not story_ids:
            return 0.0
        placeholders = ",".join("?" for _ in story_ids)
        rows = self.db.execute(
            f"SELECT score FROM shorts_performance WHERE story_id IN ({placeholders})",
            story_ids,
        ).fetchall()
        if not rows:
            return 0.0
        avg = sum(float(row["score"]) for row in rows) / len(rows)
        # Conservative feedback: history can help/hurt selection, but never dominate it.
        return round(max(-8.0, min(12.0, (avg - 50.0) * 0.24)), 2)

    def leaders(self, limit: int = 10) -> list[dict]:
        rows = self.db.execute(
            "SELECT story_id, views, likes, comments, age_hours, score "
            "FROM shorts_performance ORDER BY score DESC, views DESC LIMIT ?",
            (max(1, limit),),
        ).fetchall()
        return [dict(row) for row in rows]
