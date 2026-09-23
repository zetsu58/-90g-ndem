"""Durable scene manifests inspired by AgentTube's repairable production model."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from .video_timeline import timeline_plan


class SceneManifestStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS scene_manifests (
            story_id TEXT NOT NULL,
            scene_index INTEGER NOT NULL,
            start REAL NOT NULL,
            duration REAL NOT NULL,
            kind TEXT NOT NULL,
            subject TEXT NOT NULL,
            motion TEXT NOT NULL,
            transition TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'planned',
            asset_path TEXT,
            narration_path TEXT,
            revision INTEGER NOT NULL DEFAULT 1,
            metadata TEXT NOT NULL DEFAULT '{}',
            updated_at REAL NOT NULL,
            PRIMARY KEY(story_id, scene_index)
        )""")
        self.db.commit()

    def __enter__(self): return self
    def __exit__(self, *_): self.db.close()

    def plan(self, story_id: str, title: str, target_seconds: float = 24.0) -> list[dict]:
        plan = timeline_plan(title, target_seconds)
        now = time.time()
        with self.db:
            for index, shot in enumerate(plan["shots"]):
                self.db.execute("""INSERT INTO scene_manifests
                    (story_id,scene_index,start,duration,kind,subject,motion,transition,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(story_id,scene_index) DO UPDATE SET
                    start=excluded.start,duration=excluded.duration,kind=excluded.kind,
                    subject=excluded.subject,motion=excluded.motion,transition=excluded.transition,
                    metadata=excluded.metadata,updated_at=excluded.updated_at""",
                    (story_id,index,shot["start"],shot["duration"],shot["kind"],shot["subject"],
                     shot["motion"],shot["transition"],json.dumps({"title": title},ensure_ascii=False),now))
        return self.scenes(story_id)

    def scenes(self, story_id: str) -> list[dict]:
        rows=self.db.execute("SELECT * FROM scene_manifests WHERE story_id=? ORDER BY scene_index",(story_id,)).fetchall()
        return [dict(row) for row in rows]

    def mark_asset(self, story_id: str, scene_index: int, *, asset_path: str | None = None,
                   narration_path: str | None = None, state: str = "ready") -> None:
        with self.db:
            self.db.execute("""UPDATE scene_manifests SET asset_path=COALESCE(?,asset_path),
                narration_path=COALESCE(?,narration_path),state=?,revision=revision+1,updated_at=?
                WHERE story_id=? AND scene_index=?""",
                (asset_path,narration_path,state,time.time(),story_id,scene_index))

    def repairable(self, story_id: str) -> list[dict]:
        rows=self.db.execute("""SELECT * FROM scene_manifests
            WHERE story_id=? AND state IN ('planned','failed','stale') ORDER BY scene_index""",(story_id,)).fetchall()
        return [dict(row) for row in rows]
