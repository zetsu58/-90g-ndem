from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import Settings
from .service import run_once

_lock = threading.Lock()
_state = {"running": False, "last_result": None, "last_error": None}


def _scan() -> None:
    if not _lock.acquire(blocking=False):
        return
    _state["running"] = True
    try:
        _state["last_result"] = run_once(Settings())
        _state["last_error"] = None
    except Exception as exc:
        _state["last_error"] = str(exc)
    finally:
        _state["running"] = False
        _lock.release()


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/health"}:
            self._reply(200, {"status": "ok", **_state})
            return
        if self.path == "/run":
            if _state["running"]:
                self._reply(202, {"status": "already-running"})
                return
            threading.Thread(target=_scan, daemon=True).start()
            self._reply(202, {"status": "started"})
            return
        self._reply(404, {"error": "not-found"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args)


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
