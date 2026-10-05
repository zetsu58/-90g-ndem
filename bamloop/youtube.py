from __future__ import annotations

import os
import time
import httplib2
from functools import partial
from pathlib import Path
from production.youtube_auth import SCOPES, authorized_client, channel_preflight
from production.publishing_policy import bamloop_env, require_format


def _enabled() -> bool:
    return bamloop_env("ENABLED", "false").casefold() in {"1", "true", "yes", "on"}


def credentials_ready() -> bool:
    return _enabled() and all(
        bamloop_env(name)
        for name in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
    )


def refresh_credentials():
    """Verify OAuth before reserving a ledger slot or starting an upload."""
    if not credentials_ready():
        raise RuntimeError("BAMLOOP YouTube credentials are not configured")
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    credentials = Credentials(
        token=None,
        refresh_token=bamloop_env("REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=bamloop_env("CLIENT_ID"),
        client_secret=bamloop_env("CLIENT_SECRET"),
        scopes=SCOPES,
    )
    credentials.refresh(partial(Request(), timeout=30))
    return credentials


def verify_channel(credentials):
    return channel_preflight(credentials, bamloop_env('EXPECTED_CHANNEL_ID'))


def upload(path: Path, metadata: dict, *, credentials=None) -> str:
    require_format(str(metadata.get("content_format") or "short"))
    from .meme_catalog import require_reviewed_meme
    require_reviewed_meme(metadata)
    if not credentials_ready():
        raise RuntimeError("BAMLOOP YouTube credentials are not configured")
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    if credentials is None:
        credentials = refresh_credentials()
    youtube = authorized_client(credentials)
    privacy = bamloop_env("PRIVACY_STATUS", "private").casefold()
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
