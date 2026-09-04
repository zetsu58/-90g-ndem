from __future__ import annotations

import base64
import os
from pathlib import Path

from .base import PublishResult
from .x_news import XNewsPost


def x_credentials_ready() -> bool:
    names = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
    return all(os.getenv(name, "").strip() for name in names)


def _oauth_client():
    from requests_oauthlib import OAuth1Session

    return OAuth1Session(
        os.environ["X_API_KEY"],
        client_secret=os.environ["X_API_SECRET"],
        resource_owner_key=os.environ["X_ACCESS_TOKEN"],
        resource_owner_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )


def _upload_image(client, image_path: str) -> str:
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"X image does not exist: {image_path}")
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("X image exceeds the 5 MB API limit")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    response = client.post(
        "https://api.x.com/2/media/upload",
        json={"media": encoded, "media_category": "tweet_image"},
        timeout=30,
    )
    response.raise_for_status()
    media_id = str(response.json().get("data", {}).get("id", ""))
    if not media_id:
        raise RuntimeError("X media upload response did not contain a media id")
    return media_id


def build_x_transport():
    """Build the live X transport from environment secrets."""
    if not x_credentials_ready():
        return None

    def transport(post: XNewsPost) -> PublishResult:
        try:
            client = _oauth_client()
            payload: dict[str, object] = {"text": post.text}
            if post.image_path:
                media_id = _upload_image(client, post.image_path)
                payload["media"] = {"media_ids": [media_id]}

            response = client.post(
                "https://api.x.com/2/tweets",
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            tweet_id = str(response.json().get("data", {}).get("id", ""))
            return PublishResult(
                ok=bool(tweet_id),
                provider="x",
                external_id=tweet_id,
                url=f"https://x.com/i/web/status/{tweet_id}" if tweet_id else "",
                error="" if tweet_id else "X response did not contain a tweet id",
            )
        except ImportError:
            return PublishResult(ok=False, provider="x", error="requests-oauthlib is not installed")
        except Exception as exc:
            return PublishResult(ok=False, provider="x", error=str(exc))

    return transport
