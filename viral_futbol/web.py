from __future__ import annotations

import json
import os
import re
import threading
import time
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from production.public_pages import public_page
from .config import Settings

VERSION = os.getenv("RELEASE_VERSION", "90gundem-2026.09-release")
_lock = threading.Lock()
_state = {"running": False, "last_result": None, "last_error": None, "last_started_at": None, "last_finished_at": None, "remotion_smoke": None, "cycle_stage": None, "cycle_stage_at": None}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_cycle() -> None:
    try:
        from scripts.run_worker import cycle
        _state["last_result"] = cycle(lambda stage: _state.update({"cycle_stage": stage, "cycle_stage_at": _timestamp()}))
        _state["last_error"] = None
    except Exception as exc:
        _state["last_error"] = type(exc).__name__
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
    from production.publishing_policy import shorts_only, unified_channel
    from .publishers.x_transport import x_credentials_ready
    from .youtube_publisher import YouTubeConfig
    from production.youtube_auth import AUTH_STATUS
    settings = Settings()
    youtube = YouTubeConfig.from_env()
    from production.queue import PublishQueue, persistent_render_path, publishing_storage_ready, direct_publish_enabled
    from production.github_ledger import required as ledger_required, ready as ledger_ready
    try:
        with PublishQueue(settings.db_path, 'viral_futbol') as queue:
            scope = "channel IN ('viral_futbol','bamloop')" if unified_channel() else "channel='viral_futbol'"
            counts=queue.db.execute(f"SELECT upload_state, COUNT(*) FROM publish_queue WHERE {scope} GROUP BY upload_state").fetchall()
            by_state={row[0]:row[1] for row in counts}
            last_upload=queue.db.execute(f"SELECT upload_state,last_error,youtube_video_id FROM publish_queue WHERE {scope} ORDER BY COALESCE(published_at,NULLIF(scheduled_at,0),created_at) DESC LIMIT 1").fetchone()
            # Queue exceptions are stored as type names; never serve raw HTTP
            # bodies, media URLs, or arbitrary error strings from this endpoint.
            error_type = None
            if last_upload and last_upload['last_error']:
                candidate = str(last_upload['last_error'])
                if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}', candidate):
                    error_type = candidate
                elif candidate.startswith('Quality gate:'):
                    error_type = 'QualityGate'
                else:
                    error_type = 'UploadOrLedgerError'
            publishing = {**queue.counts(), 'next_short_slot': queue.next_slot(content_format='short'), 'next_video_slot': queue.next_slot(content_format='video'),
              'render_count':queue.db.execute(f"SELECT COUNT(*) FROM publish_queue WHERE {scope}").fetchone()[0],
              'upload_count':by_state.get('published',0), 'failure_count':by_state.get('failed',0)+by_state.get('quality_blocked',0),
              'last_upload_state':last_upload['upload_state'] if last_upload else None,
              'last_upload_error_type':error_type,
              'last_uploaded_video_id':last_upload['youtube_video_id'] if last_upload and last_upload['upload_state']=='published' else None,
              'db_persistence_ready': persistent_render_path(settings.db_path)}
            if unified_channel():
                publishing['queue_size'] = sum(by_state.get(state, 0) for state in ('queued','failed','uploading','uncertain'))
                publishing['queue_by_source'] = {row[0]: row[1] for row in queue.db.execute(f"SELECT channel,COUNT(*) FROM publish_queue WHERE {scope} AND upload_state IN ('queued','failed','uploading','uncertain') GROUP BY channel")}
    except Exception:
        publishing = {'queue_size': None, 'videos_today': None, 'next_short_slot': None, 'next_video_slot': None, 'db_persistence_ready': False}
    return {
        **dict(_state), **publishing, **AUTH_STATUS['viral_futbol'],
        'deploy_commit': os.getenv('RENDER_GIT_COMMIT') if re.fullmatch(r'[0-9a-f]{40}', os.getenv('RENDER_GIT_COMMIT','')) else None,
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
            "youtube_expected_channel_id": os.getenv("YOUTUBE_EXPECTED_CHANNEL_ID") or None,
            "shorts_min_width": os.getenv("SHORTS_MIN_WIDTH", "720"),
            "shorts_min_height": os.getenv("SHORTS_MIN_HEIGHT", "1280"),
            "direct_publish_enabled": direct_publish_enabled(),
            "github_ledger_required": ledger_required(),
            "github_ledger_ready": ledger_ready() if ledger_required() else False,
            "autostart_worker": os.getenv("NEWS_AUTOSTART_WORKER", "true").casefold() in {"1", "true", "yes", "on"},
            "unified_youtube_channel": unified_channel(),
            "content_sources": ["viral_futbol", "bamloop"] if unified_channel() else ["viral_futbol"],
            "shorts_only_mode": shorts_only(),
            "longform_enabled": not shorts_only() and os.getenv("VIRAL_LONGFORM_ENABLED",os.getenv("LONGFORM_ENABLED","false")).casefold() in {"1","true","yes","on"},
            "longform_interval_hours": os.getenv("VIRAL_LONGFORM_INTERVAL_HOURS",os.getenv("LONGFORM_INTERVAL_HOURS","24")),
            "release_ready": (not settings.dry_run) and youtube.ready and publishing_storage_ready(settings.db_path) and (not ledger_required() or ledger_ready()),
            "db_persistent_path": settings.db_path.startswith("/data/"),
        },
    }



def _remotion_smoke() -> dict:
    from production.remotion_bridge import render as render_remotion
    with tempfile.TemporaryDirectory(prefix="remotion-smoke-") as tmp:
        root = Path(tmp)
        image = root / "frame.png"
        output = root / "smoke.mp4"
        from PIL import Image
        Image.new("RGB", (64, 64), (24, 96, 180)).save(image)
        diagnostic = {}
        ok = render_remotion(
            output=output,
            title="90+ GUNDEM",
            caption="REMOTION SMOKE TEST",
            duration=0.1,
            kind="smoke",
            media=[image],
            force=True,
            timeout_seconds=45,
            diagnostic=diagnostic,
        )
        return {
            "ok": ok,
            "engine": "remotion",
            "bytes": output.stat().st_size if ok and output.exists() else 0,
            "diagnostic": diagnostic,
        }

class Handler(BaseHTTPRequestHandler):
    def _reply_html(self, body: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

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
        page = public_page("viral_futbol", path)
        if page is not None:
            self._reply_html(page)
            return
        if path in {'/health','/healthz','/'}:
            self._reply(200, {'status':'ok','version':VERSION})
            return
        if path == '/ready':
            # Keep the process health separate from its ability to publish safely.
            # A Free Render filesystem can disappear on restart.
            from production.queue import publishing_storage_ready
            from production.github_ledger import required as ledger_required, ready as ledger_ready
            ready = os.getenv('YOUTUBE_ENABLED','false').casefold() not in {'1','true','yes','on'} or (publishing_storage_ready(Settings().db_path) and (not ledger_required() or ledger_ready()))
            self._reply(200 if ready else 503, {'status':'ready' if ready else 'persistence_required','version':VERSION})
            return
        if path == '/status':
            self._reply(200, {"status": "ok", "version": VERSION, **public_status()})
            return
        if path == "/version":
            self._reply(200, {"status": "ok", "version": VERSION})
            return
        if path == "/remotion-smoke":
            if not self._authorized():
                self._reply(401, {"error": "unauthorized", "version": VERSION})
                return
            result = _remotion_smoke()
            self._reply(200 if result.get("ok") else 503, {"version": VERSION, **result})
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

    def do_HEAD(self) -> None:
        path = urlsplit(self.path).path.rstrip('/') or '/'
        if path == '/ready':
            from production.queue import publishing_storage_ready
            from production.github_ledger import required as ledger_required, ready as ledger_ready
            ready = os.getenv('YOUTUBE_ENABLED','false').casefold() not in {'1','true','yes','on'} or (publishing_storage_ready(Settings().db_path) and (not ledger_required() or ledger_ready()))
            self.send_response(200 if ready else 503)
        else:
            self.send_response(200 if path in {'/','/health','/healthz','/status'} or public_page("viral_futbol", path) is not None else 404)
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args, flush=True)


def _autonomous_loop() -> None:
    interval = max(30, int(os.getenv("NEWS_WORKER_INTERVAL_SECONDS", "180")))
    while True:
        start_cycle()
        time.sleep(interval)


def _startup_remotion_smoke() -> None:
    _state["remotion_smoke"] = {"ok": None, "engine": "remotion", "state": "pending"}
    time.sleep(8)
    _state["remotion_smoke"] = {"ok": None, "engine": "remotion", "state": "running", "started_at": _timestamp()}
    try:
        result = _remotion_smoke()
        _state["remotion_smoke"] = {**result, "state": "success" if result.get("ok") else "failure", "finished_at": _timestamp()}
    except Exception as exc:
        _state["remotion_smoke"] = {"ok": False, "engine": "remotion", "state": "failure", "error": type(exc).__name__, "detail": str(exc)[:240], "finished_at": _timestamp()}

def _bootstrap_database() -> None:
    """Create every runtime-owned table before autonomous workers start."""
    settings = Settings()
    from .service import Store
    from .scene_manifest import SceneManifestStore
    from .youtube_publisher import PublicationStore
    from production.queue import PublishQueue
    with Store(settings.db_path):
        pass
    with SceneManifestStore(settings.db_path):
        pass
    with PublicationStore(settings.db_path):
        pass
    with PublishQueue(settings.db_path, "viral_futbol"):
        pass

def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    _bootstrap_database()
    if os.getenv("NEWS_AUTOSTART_WORKER", "true").casefold() in {"1", "true", "yes", "on"}:
        threading.Thread(target=_autonomous_loop, name="viral-futbol-worker", daemon=True).start()
    # Remotion rendering is optional on constrained hosts; FFmpeg remains the production renderer.
    if os.getenv("REMOTION_SMOKE_ON_START", "false").casefold() in {"1", "true", "yes", "on"}:
        threading.Thread(target=_startup_remotion_smoke, name="remotion-smoke", daemon=True).start()
    else:
        _state["remotion_smoke"] = {"ok": None, "engine": "remotion", "state": "disabled", "reason": "ffmpeg-production-renderer"}
    print(f"ViralFutbol web service starting: {VERSION} port={port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
