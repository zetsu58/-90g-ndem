"""Shared, secret-safe YouTube upload authentication and channel preflight."""

from __future__ import annotations

import re

SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
)
_ERRORS = frozenset({"invalid_grant", "invalid_client", "deleted_client", "unauthorized_client", "invalid_scope", "redirect_uri_mismatch", "access_denied"})
AUTH_STATUS = {"viral_futbol": {}, "bamloop": {}}


def record_auth(profile: str, *, channel: dict[str, str] | None = None, error: str | None = None) -> None:
    AUTH_STATUS[profile] = {
        "youtube_auth_ready": channel is not None,
        "youtube_channel_id": channel["id"] if channel else None,
        "youtube_channel_title": channel["title"] if channel else None,
        "oauth_refresh_error": error,
    }


class ChannelMismatch(RuntimeError):
    pass


class ChannelNotConfigured(RuntimeError):
    pass


def safe_oauth_error(exc: Exception) -> str:
    """Return only a known provider code, never its response or credentials."""
    if isinstance(exc, ChannelMismatch):
        return "youtube_channel_mismatch"
    if isinstance(exc, ChannelNotConfigured):
        return "youtube_expected_channel_missing"
    for arg in getattr(exc, "args", ()):
        if isinstance(arg, dict):
            code = arg.get("error")
            if isinstance(code, str) and code in _ERRORS:
                return code
        elif isinstance(arg, str):
            match = re.search(r"\b(?:invalid_grant|invalid_client|deleted_client|unauthorized_client|invalid_scope|redirect_uri_mismatch|access_denied)\b", arg)
            if match:
                return match.group(0)
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return "oauth_network_error"
    return "oauth_refresh_failed"


def authorized_client(credentials):
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build

    transport = httplib2.Http(timeout=60)
    # Resumable uploads return 308 Resume Incomplete without a Location header.
    # googleapiclient handles that response and advances the byte range, but
    # httplib2 otherwise tries to follow it as a redirect and raises first.
    transport.redirect_codes = transport.redirect_codes - {308}
    return build("youtube", "v3", http=AuthorizedHttp(credentials, http=transport), cache_discovery=False)


def channel_preflight(credentials, expected_id: str) -> dict[str, str]:
    """Confirm the authenticated channel before consuming a ledger slot."""
    if not expected_id or not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", expected_id):
        raise ChannelNotConfigured("Expected channel ID is required")
    response = authorized_client(credentials).channels().list(part="id,snippet", mine=True).execute()
    items = response.get("items") or []
    if len(items) != 1 or items[0].get("id") != expected_id:
        raise ChannelMismatch("Authenticated YouTube channel does not match configured channel")
    return {"id": expected_id, "title": str((items[0].get("snippet") or {}).get("title") or "")[:100]}


def verify_public_upload(credentials, video_id: str) -> bool:
    """Query the actual upload; a returned insert ID alone cannot prove public visibility."""
    response = authorized_client(credentials).videos().list(part="id,status,processingDetails", id=video_id).execute()
    items = response.get("items") or []
    return len(items) == 1 and items[0].get("id") == video_id and (items[0].get("status") or {}).get("privacyStatus") == "public"
