from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .base import PublishResult


@dataclass(frozen=True)
class YouTubeUpload:
    video_path: str
    title: str
    description: str
    privacy_status: str = "private"


class YouTubePublisher:
    """Server-side YouTube publisher boundary.

    OAuth transport is injected after account authorization. Private is the
    safe default for the first autonomous end-to-end tests.
    """

    def __init__(self, transport: Callable[[YouTubeUpload], PublishResult] | None = None, *, dry_run: bool = True) -> None:
        self.transport = transport
        self.dry_run = dry_run

    def publish(self, upload: YouTubeUpload) -> PublishResult:
        if not Path(upload.video_path).is_file() and not self.dry_run:
            return PublishResult(ok=False, provider="youtube", error="Video file not found")
        if self.dry_run:
            return PublishResult(ok=True, provider="youtube", external_id="dry-run")
        if self.transport is None:
            return PublishResult(ok=False, provider="youtube", error="YouTube OAuth transport is not configured")
        try:
            return self.transport(upload)
        except Exception as exc:
            return PublishResult(ok=False, provider="youtube", error=str(exc))
