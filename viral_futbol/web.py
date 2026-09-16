from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

VERSION = "viral-futbol-female-fast-cuts-private-2026-09-16-v13"
_lock = threading.Lock()
_state = {"running": False, "last_result": None, "last_error": None, "last_started_at": None, "last_finished_at": None}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_cycle() -> None:
    try:
        from scripts.run_worker import cycle
        _state["last_result"] = cycle()
        _state["last_error"] = None
    except Exception as exc:
        _state["last_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _state["last_finished_at"] = _timestamp()
        _state["running"] = False
        _lock.release()


def start_cycle() -> bool:
    if not _lock.acquire(blocking=False):
        return False
    _state["running"] = True
    _state["last_started_at"] = _timestamp()
    try:
        threading.Thread(target=_run_cycle, name="90gundem-cycle", daemon=True).start()
    except Exception:
        _state["running"] = False
        _lock.release()
        raise
    return True


def public_status() -> dict:
    from .config import Settings
    from .publishers.x_transport import x_credentials_ready
    from .youtube_publisher import YouTubeConfig
    settings = Settings()
    youtube = YouTubeConfig.from_env()
    return {
        **dict(_state),
        "configuration": {
            "dry_run": settings.dry_run,
            "video_engine": settings.video_engine,
            "lite_video_dir": settings.lite_video_dir,
            "x_publish_enabled": os.getenv("X_PUBLISH_ENABLED", "false").casefold() in {"1", "true", "yes", "on"},
            "x_credentials_ready": x_credentials_ready(),
            "x_daily_post_limit": int(os.getenv("X_DAILY_POST_LIMIT", "20")),
            "poll_seconds": settings.poll_seconds,
            "x_max_age_minutes": settings.x_max_age_minutes,
            "shorts_max_age_minutes": settings.shorts_max_age_minutes,
            "youtube_enabled": youtube.enabled,
            "youtube_credentials_ready": youtube.ready,
            "youtube_privacy_status": youtube.privacy_status,
            "autostart_worker": os.getenv("NEWS_AUTOSTART_WORKER", "true").casefold() in {"1", "true", "yes", "on"},
        },
    }


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        secret = os.getenv("CYCLE_SECRET", "").strip()
        if not secret:
            return False
        supplied = self.headers.get("Authorization", "")
        return supplied == f"Bearer {secret}"

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path in {"/", "/health", "/status"}:
            self._reply(200, {"status": "ok", "version": VERSION, **public_status()})
            return
        if path == "/version":
            self._reply(200, {"status": "ok", "version": VERSION})
            return
        if path == "/cycle":
            if not self._authorized():
                self._reply(401, {"error": "unauthorized", "version": VERSION})
                return
            if not start_cycle():
                self._reply(202, {"status": "already-running", "accepted": True, "version": VERSION})
                return
            self._reply(202, {"status": "started", "accepted": True, "version": VERSION})
            return
        self._reply(404, {"error": "not-found", "path": path, "version": VERSION})

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args, flush=True)


def _autonomous_loop() -> None:
    interval = max(30, int(os.getenv("NEWS_WORKER_INTERVAL_SECONDS", "180")))
    while True:
        start_cycle()
        time.sleep(interval)


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    if os.getenv("NEWS_AUTOSTART_WORKER", "true").casefold() in {"1", "true", "yes", "on"}:
        threading.Thread(target=_autonomous_loop, name="viral-futbol-worker", daemon=True).start()
    print(f"ViralFutbol web service starting: {VERSION} port={port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
