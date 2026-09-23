"""Collect BAMLOOP YouTube performance and feed the shared learning loop."""
from __future__ import annotations
import os, time
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from production.queue import PublishQueue
from viral_futbol.performance_learning import PerformanceSample, PerformanceStore
from viral_futbol.scene_performance import record_story_scene_snapshot
from viral_futbol.retention_collector import collect_video_retention


def _client():
    names=("MEME_YOUTUBE_CLIENT_ID","MEME_YOUTUBE_CLIENT_SECRET","MEME_YOUTUBE_REFRESH_TOKEN")
    if not all(os.getenv(n,"").strip() for n in names): return None
    creds=Credentials(token=None,refresh_token=os.environ[names[2]].strip(),
        token_uri="https://oauth2.googleapis.com/token",client_id=os.environ[names[0]].strip(),
        client_secret=os.environ[names[1]].strip(),
        scopes=["https://www.googleapis.com/auth/youtube.readonly"])
    return build("youtube","v3",credentials=creds,cache_discovery=False)


def collect(db_path: str, limit: int = 25) -> dict:
    youtube=_client()
    if youtube is None: return {"ready":False,"collected":0}
    with PublishQueue(db_path,"bamloop") as queue:
        rows=queue.db.execute("""SELECT content_id,youtube_video_id,published_at FROM publish_queue
            WHERE channel='bamloop' AND upload_state='published' AND youtube_video_id IS NOT NULL
            ORDER BY published_at DESC LIMIT ?""",(max(1,limit),)).fetchall()
    ids=[str(r["youtube_video_id"]) for r in rows]
    if not ids: return {"ready":True,"collected":0}
    response=youtube.videos().list(part="statistics",id=",".join(ids)).execute()
    stats={str(x["id"]):x.get("statistics",{}) for x in response.get("items",[])}
    collected=0
    with PerformanceStore(db_path) as store:
        for row in rows:
            s=stats.get(str(row["youtube_video_id"]))
            if not s: continue
            age=max(0.0,(time.time()-float(row["published_at"] or time.time()))/3600)
            sample=PerformanceSample(str(row["content_id"]),int(s.get("viewCount",0)),
                int(s.get("likeCount",0)),int(s.get("commentCount",0)),age)
            score=store.record(sample)
            record_story_scene_snapshot(db_path,sample.story_id,age_hours=age,views=sample.views,
                likes=sample.likes,comments=sample.comments,performance_score=score)
            try:
                collect_video_retention(db_path,story_id=sample.story_id,video_id=str(row["youtube_video_id"]),
                    client_id=os.environ["MEME_YOUTUBE_CLIENT_ID"].strip(),
                    client_secret=os.environ["MEME_YOUTUBE_CLIENT_SECRET"].strip(),
                    refresh_token=os.environ["MEME_YOUTUBE_REFRESH_TOKEN"].strip(),
                    published_at=float(row["published_at"] or time.time()))
            except Exception:
                # Retention is advisory and may lag behind publication.
                pass
            collected+=1
    return {"ready":True,"collected":collected}
