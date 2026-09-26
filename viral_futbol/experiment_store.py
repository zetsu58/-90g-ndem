"""Durable observability for creative exploit/explore experiments."""
from __future__ import annotations
import sqlite3, time
from pathlib import Path

class ExperimentStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(db_path,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS creative_experiments(
          story_id TEXT PRIMARY KEY, channel TEXT NOT NULL, mode TEXT NOT NULL,
          motion TEXT, transition_name TEXT, bucket INTEGER, created_at REAL NOT NULL)""")
        self.db.commit()
    def __enter__(self): return self
    def __exit__(self,*_): self.db.close()
    def record(self, story_id: str, channel: str, choice: dict):
        with self.db:
            self.db.execute("""INSERT INTO creative_experiments VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(story_id) DO UPDATE SET channel=excluded.channel,mode=excluded.mode,
            motion=excluded.motion,transition_name=excluded.transition_name,bucket=excluded.bucket""",
            (story_id,channel,choice.get("mode","baseline"),choice.get("motion"),
             choice.get("transition"),choice.get("bucket"),time.time()))
    def summary(self, channel: str):
        # Fresh ephemeral SQLite databases may not have analytics tables yet.
        from .performance_learning import PerformanceStore
        with PerformanceStore(str(self.db.execute('PRAGMA database_list').fetchone()[2])):
            pass
        rows=self.db.execute("""SELECT e.mode,COUNT(DISTINCT e.story_id) videos,
          AVG(p.score) avg_score
          FROM creative_experiments e LEFT JOIN shorts_performance p ON p.story_id=e.story_id
          WHERE e.channel=? GROUP BY e.mode ORDER BY e.mode""",(channel,)).fetchall()
        return [dict(r) for r in rows]
