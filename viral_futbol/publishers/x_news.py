from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from .base import PublishResult


@dataclass(frozen=True)
class XNewsPost:
    text: str
    source_url: str
    image_path: str = ""


def _include_source_url() -> bool:
    return os.getenv("X_INCLUDE_SOURCE_URL", "false").casefold() in {"1", "true", "yes", "on"}


def build_x_news_post(title: str, source_url: str, *, max_chars: int = 275) -> XNewsPost:
    """Create compact Turkish news copy; zero-budget mode omits the clickable URL."""
    clean = " ".join(title.split())
    suffix = ("\n\nKaynak: " + source_url) if _include_source_url() else "\n\n#SonDakika #Gundem"
    room = max(40, max_chars - len(suffix))
    if len(clean) > room:
        clean = clean[: max(1, room - 1)].rstrip() + "…"
    return XNewsPost(text=clean + suffix, source_url=source_url)


class XNewsPublisher:
    def __init__(self, transport: Callable[[XNewsPost], PublishResult] | None = None, *, dry_run: bool = True) -> None:
        self.transport = transport
        self.dry_run = dry_run

    def publish(self, post: XNewsPost) -> PublishResult:
        if self.dry_run:
            return PublishResult(ok=True, provider="x", external_id="dry-run")
        if self.transport is None:
            return PublishResult(ok=False, provider="x", error="X transport is not configured")
        try:
            return self.transport(post)
        except Exception as exc:
            return PublishResult(ok=False, provider="x", error=str(exc))
