"""Deployment policy shared by both producers; contains no credentials."""
import os


def unified_channel():
    return os.getenv("UNIFIED_YOUTUBE_CHANNEL", "false").casefold() in {"1", "true", "yes", "on"}


def shorts_only():
    return os.getenv("SHORTS_ONLY_MODE", "false").casefold() in {"1", "true", "yes", "on"}


def capacity_channel(source):
    return "viral_futbol" if unified_channel() and source in {"viral_futbol", "bamloop"} else source


def bamloop_env(suffix, default=""):
    prefix = "YOUTUBE_" if unified_channel() else "MEME_YOUTUBE_"
    return os.getenv(prefix + suffix, default).strip()


def require_format(content_format):
    if shorts_only() and content_format != "short":
        raise ValueError("longform_disabled_by_shorts_only_policy")
