from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

from .base import PublishResult
from .x_news import XNewsPost


class XApiTransport:
    """Minimal server-side X transport using bearer access token.

    The token is read from the runtime environment only. Media upload URL and
    post URL are configurable so API-version changes do not require rewriting
    the publisher layer.
    """

    def __init__(self) -> None:
        self.token = os.getenv("X_ACCESS_TOKEN", "").strip()
        self.post_url = os.getenv("X_POST_URL", "https://api.x.com/2/tweets").strip()
        self.media_url = os.getenv("X_MEDIA_UPLOAD_URL", "").strip()
        self.timeout = int(os.getenv("X_REQUEST_TIMEOUT", "30"))

    def _request(self, url: str, payload: dict) -> dict:
        if not self.token:
            raise RuntimeError("X_ACCESS_TOKEN is not configured")
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "ViralFutbol/3.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise RuntimeError(f"X API HTTP {exc.code}: {detail}") from exc

    def _upload_media(self, image_path: str) -> str:
        # Kept opt-in because X media-upload authentication/endpoints can vary
        # by API access tier. Text publishing works independently.
        if not image_path or not self.media_url:
            return ""
        path = Path(image_path)
        if not path.is_file():
            raise RuntimeError(f"X image not found: {image_path}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        payload = {
            "media_data": __import__("base64").b64encode(path.read_bytes()).decode("ascii"),
            "media_type": mime,
        }
        result = self._request(self.media_url, payload)
        return str(result.get("media_id_string") or result.get("data", {}).get("id") or "")

    def __call__(self, post: XNewsPost) -> PublishResult:
        try:
            media_id = self._upload_media(post.image_path)
            payload: dict = {"text": post.text}
            if media_id:
                payload["media"] = {"media_ids": [media_id]}
            result = self._request(self.post_url, payload)
            external_id = str(result.get("data", {}).get("id") or result.get("id") or "")
            if not external_id:
                return PublishResult(ok=False, provider="x", error="X API returned no post id")
            return PublishResult(ok=True, provider="x", external_id=external_id)
        except Exception as exc:
            return PublishResult(ok=False, provider="x", error=str(exc))
