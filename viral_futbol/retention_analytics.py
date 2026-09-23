"""YouTube Analytics audience-retention curves mapped onto durable scene windows."""
from __future__ import annotations
import sqlite3, time
from pathlib import Path
from viral_futbol.scene_manifest import SceneManifestStore


class RetentionStore:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(db_path,timeout=30); self.db.row_factory=sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("""CREATE TABLE IF NOT EXISTS video_retention_points(
          story_id TEXT NOT NULL, video_id TEXT NOT NULL, elapsed_ratio REAL NOT NULL,
          audience_watch_ratio REAL, relative_retention REAL, stopped_watching REAL,
          captured_at REAL NOT NULL, PRIMARY KEY(story_id,video_id,elapsed_ratio))""")
        self.db.commit()
    def __enter__(self): return self
    def __exit__(self,*_): self.db.close()

    def record(self, story_id, video_id, points):
        now=time.time()
        with self.db:
            for p in points:
                self.db.execute("""INSERT INTO video_retention_points VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(story_id,video_id,elapsed_ratio) DO UPDATE SET
                audience_watch_ratio=excluded.audience_watch_ratio,
                relative_retention=excluded.relative_retention,
                stopped_watching=excluded.stopped_watching,captured_at=excluded.captured_at""",
                (story_id,video_id,p["elapsed_ratio"],p.get("audience_watch_ratio"),
                 p.get("relative_retention"),p.get("stopped_watching"),now))

    def scene_summary(self, story_id: str):
        with SceneManifestStore(self.db.execute("PRAGMA database_list").fetchone()[2]) as manifests:
            scenes=manifests.scenes(story_id)
        if not scenes: return []
        duration=max(float(s["start"])+float(s["duration"]) for s in scenes)
        points=self.db.execute("SELECT * FROM video_retention_points WHERE story_id=? ORDER BY elapsed_ratio",(story_id,)).fetchall()
        out=[]
        for scene in scenes:
            lo=float(scene["start"])/duration; hi=(float(scene["start"])+float(scene["duration"]))/duration
            matched=[p for p in points if lo < float(p["elapsed_ratio"]) <= hi]
            if not matched: continue
            vals=[float(p["audience_watch_ratio"]) for p in matched if p["audience_watch_ratio"] is not None]
            stops=[float(p["stopped_watching"]) for p in matched if p["stopped_watching"] is not None]
            out.append({"scene_index":scene["scene_index"],"motion":scene["motion"],"transition":scene["transition"],
                "avg_watch_ratio":round(sum(vals)/len(vals),4) if vals else None,
                "stopped_watching":round(sum(stops),2) if stops else None,"points":len(matched)})
        return out


def fetch_retention(youtube_analytics, *, video_id: str, start_date: str, end_date: str):
    response=youtube_analytics.reports().query(ids="channel==MINE",startDate=start_date,endDate=end_date,
        metrics="audienceWatchRatio,relativeRetentionPerformance,stoppedWatching",
        dimensions="elapsedVideoTimeRatio",filters=f"video=={video_id}").execute()
    headers=[h["name"] for h in response.get("columnHeaders",[])]
    points=[]
    for row in response.get("rows",[]) or []:
        d=dict(zip(headers,row))
        points.append({"elapsed_ratio":float(d["elapsedVideoTimeRatio"]),
            "audience_watch_ratio":float(d["audienceWatchRatio"]) if d.get("audienceWatchRatio") is not None else None,
            "relative_retention":float(d["relativeRetentionPerformance"]) if d.get("relativeRetentionPerformance") is not None else None,
            "stopped_watching":float(d["stoppedWatching"]) if d.get("stoppedWatching") is not None else None})
    return points
