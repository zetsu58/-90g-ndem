"""Immutable-ish 24h/7d retention snapshots for longitudinal learning."""
from __future__ import annotations
import sqlite3, time
from pathlib import Path

class RetentionSnapshotStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(db_path,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS retention_snapshots(
          story_id TEXT NOT NULL, video_id TEXT NOT NULL, bucket_hours INTEGER NOT NULL,
          elapsed_ratio REAL NOT NULL, audience_watch_ratio REAL, relative_retention REAL,
          captured_at REAL NOT NULL, PRIMARY KEY(story_id,video_id,bucket_hours,elapsed_ratio))""")
        self.db.commit()
    def __enter__(self): return self
    def __exit__(self,*_): self.db.close()
    def record(self, story_id, video_id, age_hours, points):
        bucket=24 if age_hours<=48 else 168
        now=time.time()
        with self.db:
            for p in points:
                self.db.execute("""INSERT OR REPLACE INTO retention_snapshots VALUES(?,?,?,?,?,?,?)""",
                 (story_id,video_id,bucket,float(p["elapsed_ratio"]),p.get("audience_watch_ratio"),p.get("relative_retention"),now))
        return bucket
