"""Map aggregate YouTube performance onto scene windows for conservative creative learning."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .scene_manifest import SceneManifestStore


class ScenePerformanceStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS scene_performance (
            story_id TEXT NOT NULL,
            scene_index INTEGER NOT NULL,
            snapshot_hours INTEGER NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            likes INTEGER NOT NULL DEFAULT 0,
            comments INTEGER NOT NULL DEFAULT 0,
            performance_score REAL NOT NULL DEFAULT 0,
            scene_weight REAL NOT NULL DEFAULT 0,
            updated_at REAL NOT NULL,
            PRIMARY KEY(story_id,scene_index,snapshot_hours)
        )""")
        self.db.commit()

    def __enter__(self): return self
    def __exit__(self, *_): self.db.close()

    def record_snapshot(self, story_id: str, scenes: list[dict], *, snapshot_hours: int,
                        views: int, likes: int, comments: int, performance_score: float) -> int:
        if not scenes: return 0
        # Until audience-retention curve data is available, distribute a conservative
        # prior that slightly favors the hook. This must not be presented as measured
        # per-scene retention.
        raw=[1.15 if i == 0 else max(0.75, 1.0 - i * 0.03) for i in range(len(scenes))]
        total=sum(raw) or 1.0
        now=time.time()
        with self.db:
            for i, scene in enumerate(scenes):
                weight=raw[i]/total
                self.db.execute("""INSERT INTO scene_performance
                    (story_id,scene_index,snapshot_hours,views,likes,comments,performance_score,scene_weight,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(story_id,scene_index,snapshot_hours) DO UPDATE SET
                    views=excluded.views,likes=excluded.likes,comments=excluded.comments,
                    performance_score=excluded.performance_score,scene_weight=excluded.scene_weight,
                    updated_at=excluded.updated_at""",
                    (story_id,int(scene["scene_index"]),snapshot_hours,max(0,views),max(0,likes),
                     max(0,comments),performance_score,weight,now))
        return len(scenes)

    def leaders(self, limit: int = 10) -> list[dict]:
        rows=self.db.execute("""SELECT m.kind,m.motion,m.transition,
            COUNT(*) samples, AVG(p.performance_score) avg_score
            FROM scene_performance p JOIN scene_manifests m
            ON m.story_id=p.story_id AND m.scene_index=p.scene_index
            GROUP BY m.kind,m.motion,m.transition HAVING COUNT(*) >= 3
            ORDER BY avg_score DESC LIMIT ?""",(max(1,limit),)).fetchall()
        return [dict(r) for r in rows]


def record_story_scene_snapshot(db_path: str, story_id: str, *, age_hours: float,
                                views: int, likes: int, comments: int,
                                performance_score: float) -> dict:
    bucket=24 if age_hours <= 48 else 168
    with SceneManifestStore(db_path) as manifests:
        scenes=manifests.scenes(story_id)
    with ScenePerformanceStore(db_path) as performance:
        count=performance.record_snapshot(story_id,scenes,snapshot_hours=bucket,views=views,
            likes=likes,comments=comments,performance_score=performance_score)
    return {"story_id":story_id,"snapshot_hours":bucket,"scenes_recorded":count}
