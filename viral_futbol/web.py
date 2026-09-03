from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .config import Settings
from .service import Store, run_once


VERSION = "90gundem-render-2026-09-03-v4"
_lock = threading.Lock()
_state = {
    "running": False,
    "last_result": None,
    "last_error": None,
    "last_started_at": None,
    "last_finished_at": None,
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scan_with_reservation() -> None:
    """Run one scan after the caller has atomically acquired the reservation."""
    try:
        _state["last_result"] = run_once(Settings())
        _state["last_error"] = None
    except Exception as exc:
        _state["last_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        _state["last_finished_at"] = _timestamp()
        _state["running"] = False
        _lock.release()


def start_scan() -> bool:
    """Atomically accept at most one scan and return whether it started."""
    if not _lock.acquire(blocking=False):
        return False
    _state["running"] = True
    _state["last_started_at"] = _timestamp()
    try:
        threading.Thread(
            target=_scan_with_reservation,
            name="viral-futbol-scan",
            daemon=True,
        ).start()
    except Exception:
        _state["running"] = False
        _lock.release()
        raise
    return True


def public_status() -> dict:
    status = dict(_state)
    settings = Settings()
    status["configuration"] = {
        "dry_run": settings.dry_run,
        "languages": list(settings.languages),
        "mpt_url_configured": bool(settings.mpt_url.strip()),
        "mpt_api_key_configured": bool(settings.mpt_api_key.strip()),
        "max_inflight_tasks": settings.max_inflight_tasks,
        "idempotency": "remote-drive-backed",
    }
    try:
        with Store(settings.db_path) as store:
            status["jobs"] = store.status_counts()
    except Exception as exc:
        status["jobs_error"] = f"{type(exc).__name__}: {exc}"
    return status


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path in {"/", "/health", "/status"}:
            self._reply(
                200,
                {"status": "ok", "version": VERSION, **public_status()},
            )
            return
        if path == "/version":
            self._reply(200, {"status": "ok", "version": VERSION})
            return
        if path == "/run":
            if not start_scan():
                self._reply(
                    202,
                    {
                        "status": "already-running",
                        "accepted": True,
                        "version": VERSION,
                    },
                )
                return
            self._reply(
                202,
                {"status": "started", "accepted": True, "version": VERSION},
            )
            return
        self._reply(
            404,
            {"error": "not-found", "path": path, "version": VERSION},
        )

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args, flush=True)


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    print(f"90+ Gundem web service starting: {VERSION} port={port}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
