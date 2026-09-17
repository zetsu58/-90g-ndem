from __future__ import annotations

import sqlite3
import time
from pathlib import Path


def remember_creative(db_path: str, story_id: str, hook: str | None) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(db_path, timeout=30)
    try:
        db.execute(
            """CREATE TABLE IF NOT EXISTS shorts_creatives (
                story_id TEXT PRIMARY KEY,
                hook_variant TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        db.execute(
            """INSERT INTO shorts_creatives(story_id, hook_variant, created_at)
               VALUES (?, ?, ?)
               ON CONFLICT(story_id) DO UPDATE SET
                 hook_variant=excluded.hook_variant""",
            (story_id, hook or "direct", time.time()),
        )
        db.commit()
    finally:
        db.close()
