from __future__ import annotations

import os

from .news_card import render_news_card
from .publishers.x_news import XNewsPublisher, build_x_news_post
from .publishers.x_transport import build_x_transport


def x_publish_enabled() -> bool:
    return os.getenv("X_PUBLISH_ENABLED", "false").casefold() in {"1", "true", "yes", "on"}


def publish_verified_cluster(cluster, *, language: str = "tr"):
    if language != "tr" or not x_publish_enabled() or not cluster:
        return None
    transport = build_x_transport()
    if transport is None:
        return None
    story = cluster[0]
    post = build_x_news_post(story.title, story.url)
    try:
        card_path = render_news_card(story.title, story.url)
        post = type(post)(text=post.text, source_url=post.source_url, image_path=card_path)
    except Exception as exc:
        # Text publishing may continue even if image rendering fails.
        print(f"ViralFutbol X card deferred: {exc}", flush=True)
    return XNewsPublisher(transport=transport, dry_run=False).publish(post)
