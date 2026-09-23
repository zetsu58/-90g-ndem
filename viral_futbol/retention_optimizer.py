"""Evidence-gated optimizer that turns measured retention into bounded creative advice."""
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, asdict
from .retention_analytics import RetentionStore

@dataclass(frozen=True)
class RetentionAdvice:
    motion: str
    transition: str
    avg_watch_ratio: float
    samples: int
    confidence: str
    def as_dict(self): return asdict(self)

def recommended_retention_creative(db_path: str, minimum_videos: int = 3) -> RetentionAdvice | None:
    db=sqlite3.connect(db_path,timeout=30); db.row_factory=sqlite3.Row
    try:
        rows=db.execute("""SELECT m.story_id,m.motion,m.transition,
          AVG(r.audience_watch_ratio) avg_watch, COUNT(r.elapsed_ratio) points
          FROM scene_manifests m JOIN video_retention_points r
          ON r.story_id=m.story_id
          WHERE r.elapsed_ratio > (m.start/(SELECT MAX(start+duration) FROM scene_manifests x WHERE x.story_id=m.story_id))
            AND r.elapsed_ratio <= ((m.start+m.duration)/(SELECT MAX(start+duration) FROM scene_manifests x WHERE x.story_id=m.story_id))
            AND r.audience_watch_ratio IS NOT NULL
          GROUP BY m.story_id,m.scene_index,m.motion,m.transition""").fetchall()
    except sqlite3.OperationalError:
        return None
    finally: db.close()
    groups={}
    for r in rows:
        key=(r["motion"],r["transition"])
        g=groups.setdefault(key,{"videos":set(),"weighted":0.0,"points":0})
        g["videos"].add(r["story_id"]); g["weighted"]+=float(r["avg_watch"])*int(r["points"]); g["points"]+=int(r["points"])
    eligible=[(k,g) for k,g in groups.items() if len(g["videos"])>=minimum_videos and g["points"]>=30]
    if not eligible: return None
    (motion,transition),g=max(eligible,key=lambda item:item[1]["weighted"]/max(1,item[1]["points"]))
    avg=g["weighted"]/g["points"]; videos=len(g["videos"])
    return RetentionAdvice(str(motion),str(transition),round(avg,4),videos,"high" if videos>=10 else "medium")
