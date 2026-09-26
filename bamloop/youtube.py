from __future__ import annotations

import os
import time
import httplib2
from pathlib import Path


def _enabled() -> bool:
    return os.getenv("MEME_YOUTUBE_ENABLED", "false").casefold() in {"1", "true", "yes", "on"}


def credentials_ready() -> bool:
    return _enabled() and all(
        os.getenv(name, "").strip()
        for name in ("MEME_YOUTUBE_CLIENT_ID", "MEME_YOUTUBE_CLIENT_SECRET", "MEME_YOUTUBE_REFRESH_TOKEN")
    )


def upload(path: Path, metadata: dict) -> str:
    if not credentials_ready():
        raise RuntimeError("BAMLOOP YouTube credentials are not configured")
    from google.oauth2.credentials import Credentials
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials = Credentials(
        token=None,
        refresh_token=os.environ["MEME_YOUTUBE_REFRESH_TOKEN"].strip(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["MEME_YOUTUBE_CLIENT_ID"].strip(),
        client_secret=os.environ["MEME_YOUTUBE_CLIENT_SECRET"].strip(),
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    youtube = build("youtube", "v3", http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=60)), cache_discovery=False)
    privacy = os.getenv("MEME_YOUTUBE_PRIVACY_STATUS", "private").casefold()
    if privacy not in {"private", "unlisted", "public"}:
        privacy = "private"
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": str(metadata["title"])[:100],
                "description": str(metadata["description"])[:5000],
                "tags": list(metadata["tags"]),
                "categoryId": "23",
                "defaultLanguage": "tr",
            },
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        },
        media_body=MediaFileUpload(str(path), mimetype="video/mp4", resumable=True),
    )
    response = None
    deadline=time.monotonic()+300
    for _ in range(120):
        if response is not None: break
        if time.monotonic()>deadline: raise TimeoutError("YouTube upload deadline exceeded")
        _, response = request.next_chunk()
    if response is None: raise TimeoutError("YouTube upload exceeded chunk limit")
    video_id = str((response or {}).get("id") or "")
    if not video_id:
        raise RuntimeError("YouTube upload completed without a video id")
    return video_id

