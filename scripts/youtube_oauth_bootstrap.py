"""Mobile-friendly OAuth URL and code exchange, with no secrets in command arguments.

The OAuth client must allow the redirect URI used here. Run in Termux or a
trusted local Python environment. The resulting file stays local (mode 0600).
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import stat
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from production.youtube_auth import SCOPES


def authorization_url(client_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": " ".join(SCOPES), "access_type": "offline", "prompt": "consent",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)


def _post(form: dict[str, str]) -> dict:
    request = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # The response may contain confidential fields. Print only a provider code.
        from production.youtube_auth import safe_oauth_error
        try:
            payload = json.loads(exc.read(8192))
        except (ValueError, UnicodeDecodeError):
            payload = {}
        raise RuntimeError(safe_oauth_error(RuntimeError(payload))) from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate offline YouTube consent and validate its channel")
    parser.add_argument("--profile", required=True, choices=("viral", "bamloop"))
    parser.add_argument("--redirect-uri", default="https://developers.google.com/oauthplayground")
    parser.add_argument("--exchange", action="store_true", help="exchange a consent code after browser approval")
    args = parser.parse_args()
    key = "YOUTUBE" if args.profile == "viral" else "MEME_YOUTUBE"
    client_id = os.getenv(f"{key}_CLIENT_ID") or input("OAuth client ID (not a secret): ").strip()
    if not client_id:
        parser.error("An OAuth client ID is required")
    if not args.exchange:
        print("Open on Android Chrome and approve the intended YouTube channel:\n" + authorization_url(client_id, args.redirect_uri))
        print("Return with --exchange to validate and store the refresh token locally.")
        return
    secret = os.getenv(f"{key}_CLIENT_SECRET") or getpass.getpass("OAuth client secret (hidden): ")
    code = getpass.getpass("Authorization code from redirect URL (hidden): ")
    result = _post({"client_id": client_id, "client_secret": secret, "code": code,
                    "redirect_uri": args.redirect_uri, "grant_type": "authorization_code"})
    refresh = result.get("refresh_token")
    if not refresh:
        raise RuntimeError("Google returned no offline refresh token; retry consent with prompt=consent")
    # Prove that this exact client/secret/token combination can refresh.
    refreshed = _post({"client_id": client_id, "client_secret": secret,
                       "refresh_token": refresh, "grant_type": "refresh_token"})
    token = refreshed.get("access_token")
    if not token:
        raise RuntimeError("OAuth refresh did not return an access token")
    request = urllib.request.Request("https://www.googleapis.com/youtube/v3/channels?part=id%2Csnippet&mine=true",
                                     headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            channels = json.load(response).get("items") or []
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"YouTube channel check failed (HTTP {exc.code})") from None
    if len(channels) != 1 or not channels[0].get("id"):
        raise RuntimeError("The selected account does not expose exactly one YouTube channel")
    channel_id = channels[0]["id"]
    expected = os.getenv(f"{key}_EXPECTED_CHANNEL_ID", "").strip()
    if expected and expected != channel_id:
        raise RuntimeError("youtube_channel_mismatch")
    target = Path.cwd() / f"youtube_oauth_{args.profile}.json"
    if target.exists():
        raise RuntimeError("Refusing to overwrite an existing credential file")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w") as stream:
        json.dump({"profile": args.profile, "client_id": client_id, "client_secret": secret,
                   "refresh_token": refresh, "channel_id": channel_id}, stream)
    print(f"OAuth refresh and channels.list succeeded for {channel_id} ({str(channels[0].get('snippet',{}).get('title',''))[:80]}).")
    print(f"Credential bundle saved locally with private permissions: {target}")
    print(f"Set {key}_CLIENT_ID, {key}_CLIENT_SECRET, {key}_REFRESH_TOKEN and {key}_EXPECTED_CHANNEL_ID in the matching Render service, then delete this local file.")


if __name__ == "__main__":
    main()
