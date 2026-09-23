"""OAuth adapter and non-blocking retention collection shared by both channels."""
from __future__ import annotations
from datetime import datetime, timezone
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .retention_analytics import RetentionStore, fetch_retention

SCOPE="https://www.googleapis.com/auth/yt-analytics.readonly"

def analytics_client(*, client_id: str, client_secret: str, refresh_token: str):
    creds=Credentials(token=None,refresh_token=refresh_token,token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,client_secret=client_secret,scopes=[SCOPE])
    return build("youtubeAnalytics","v2",credentials=creds,cache_discovery=False)

def collect_video_retention(db_path: str, *, story_id: str, video_id: str,
                            client_id: str, client_secret: str, refresh_token: str,
                            published_at: float | None = None) -> dict:
    end=datetime.now(timezone.utc).date()
    start=datetime.fromtimestamp(published_at,timezone.utc).date() if published_at else end
    api=analytics_client(client_id=client_id,client_secret=client_secret,refresh_token=refresh_token)
    points=fetch_retention(api,video_id=video_id,start_date=start.isoformat(),end_date=end.isoformat())
    with RetentionStore(db_path) as store:
        store.record(story_id,video_id,points)
        scenes=store.scene_summary(story_id)
    return {"points":len(points),"scenes":scenes}
