from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .base import PublishResult
from .x_news import XNewsPost


def x_credentials_ready() -> bool:
    names = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    return all(os.getenv(name, "").strip() for name in names)


def build_x_transport():
    """Build an X v2 transport from environment secrets.

    OAuth signing is imported lazily so dry-run/server startup never depends on it.
    """
    if not x_credentials_ready():
        return None

    def transport(post: XNewsPost) -> PublishResult:
        try:
            from requests_oauthlib import OAuth1Session
        except ImportError:
            return PublishResult(ok=False, provider="x", error="requests-oauthlib is not installed")

        client = OAuth1Session(
            os.environ["X_API_KEY"],
            client_secret=os.environ["X_API_SECRET"],
            resource_owner_key=os.environ["X_ACCESS_TOKEN"],
            resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
        )
        try:
            response = client.post(
                "https://api.x.com/2/tweets",
                json={"text": post.text},
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            tweet_id = str(payload.get("data", {}).get("id", ""))
            return PublishResult(
                ok=bool(tweet_id),
                provider="x",
                external_id=tweet_id,
                url=f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "",
                error="" if tweet_id else "X response did not contain a tweet id",
            )
        except Exception as exc:
            return PublishResult(ok=False, provider="x", error=str(exc))

    return transport
