"""Position-aware measured retention summaries."""
from __future__ import annotations
import sqlite3

def position_retention(db_path: str, story_id: str, video_id: str | None = None) -> list[dict]:
    db=sqlite3.connect(db_path,timeout=30); db.row_factory=sqlite3.Row
    try:
        scenes=db.execute("SELECT scene_index,start,duration FROM scene_manifests WHERE story_id=? ORDER BY scene_index",(story_id,)).fetchall()
        if not scenes: return []
        total=max(float(s["start"])+float(s["duration"]) for s in scenes)
        q="SELECT video_id,elapsed_ratio,audience_watch_ratio FROM video_retention_points WHERE story_id=? AND audience_watch_ratio IS NOT NULL"
        args=[story_id]
        if video_id: q+=" AND video_id=?"; args.append(video_id)
        points=db.execute(q,args).fetchall()
        out=[]
        last=len(scenes)-1
        for i,s in enumerate(scenes):
            lo=float(s["start"])/total; hi=(float(s["start"])+float(s["duration"]))/total
            vals=[float(p["audience_watch_ratio"]) for p in points if (float(p["elapsed_ratio"])>=lo if i==0 else float(p["elapsed_ratio"])>lo) and (float(p["elapsed_ratio"])<=hi)]
            out.append({"scene_index":int(s["scene_index"]),"position":"hook" if i==0 else ("final" if i==last else "middle"),"avg_watch_ratio":round(sum(vals)/len(vals),4) if vals else None,"points":len(vals)})
        return out
    finally: db.close()
