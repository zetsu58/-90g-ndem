from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts.run_meme_worker import cycle

STATE: dict = {
    "service": "bamloop",
    "status": "starting",
    "last_run": None,
    "last_success": None,
    "last_error": None,
    "last_result": None,
}
LOCK = threading.Lock()


def _set(**values: object) -> None:
    with LOCK:
        STATE.update(values)


def worker() -> None:
    interval = max(3600, int(os.getenv("MEME_INTERVAL_SECONDS", "14400")))
    startup_delay = max(5, int(os.getenv("MEME_STARTUP_DELAY_SECONDS", "20")))
    time.sleep(startup_delay)
    while True:
        started = int(time.time())
        _set(status="working", last_run=started, last_error=None)
        try:
            result = cycle()
            _set(status="idle", last_success=int(time.time()), last_result=result)
        except Exception as exc:
            _set(status="error", last_error=f"{type(exc).__name__}: {exc}"[:500])
        elapsed = int(time.time()) - started
        time.sleep(max(60, interval - elapsed))


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in {"/", "/health", "/healthz"}:
            with LOCK:
                snapshot = dict(STATE)
            self._reply(200, snapshot)
        else:
            self._reply(404, {"error": "not_found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    _set(status="idle")
    threading.Thread(target=worker, daemon=True, name="bamloop-worker").start()
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
