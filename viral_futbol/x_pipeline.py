from __future__ import annotations

import os

from .publishers.x_news import XNewsPublisher, build_x_news_post
from .publishers.x_transport import build_x_transport


def x_publish_enabled() -> bool:
    return os.getenv("X_PUBLISH_ENABLED", "false").casefold() in {"1", "true", "yes", "on"}


def publish_verified_cluster(cluster, *, language: str = "tr"):
    """Publish one already-verified cluster to X.

    Only Turkish edition is published for now. Live posting requires the explicit
    X_PUBLISH_ENABLED switch plus all OAuth secrets; otherwise this is a safe no-op.
    """
    if language != "tr" or not x_publish_enabled() or not cluster:
        return None
    transport = build_x_transport()
    if transport is None:
        return None
    story = cluster[0]
    post = build_x_news_post(story.title, story.url)
    return XNewsPublisher(transport=transport, dry_run=False).publish(post)
