from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .base import PublishResult


@dataclass(frozen=True)
class XNewsPost:
    text: str
    source_url: str
    image_path: str = ""


def build_x_news_post(title: str, source_url: str, *, max_chars: int = 275) -> XNewsPost:
    """Create compact Turkish news copy while preserving room for the source URL."""
    clean = " ".join(title.split())
    suffix = "\n\nKaynak: " + source_url
    room = max(40, max_chars - len(suffix))
    if len(clean) > room:
        clean = clean[: max(1, room - 1)].rstrip() + "…"
    return XNewsPost(text=clean + suffix, source_url=source_url)


class XNewsPublisher:
    """Transport-neutral X publisher.

    Live OAuth/API transport is injected later. Keeping credentials outside this
    module prevents secrets from leaking into the repository and lets dry-run
    deployments work before the X account is authorized.
    """

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
