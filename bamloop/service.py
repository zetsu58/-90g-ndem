from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bamloop.pipeline import cycle, db_path, publish_pending
from production.queue import PublishQueue, persistent_render_path, publishing_storage_ready, direct_publish_enabled
from production.github_ledger import required as ledger_required, ready as ledger_ready
from bamloop.youtube import credentials_ready

STATE: dict = {
    "service": "bamloop",
    "status": "starting",
    "last_run": None,
    "running": False,
    "render_count": 0,
    "upload_count": 0,
    "failure_count": 0,
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
        _set(status="working", running=True, last_run=started, last_error=None)
        try:
            result = cycle()
            _set(status="idle", running=False, last_success=int(time.time()), last_result=result,
                last_content_type=(result.get('prepare') or {}).get('content_type'),
                render_count=STATE['render_count'] + int(bool((result.get('prepare') or {}).get('queued'))),
                upload_count=STATE['upload_count'] + sum(int((result.get(k) or {}).get('uploaded',0)) for k in ('publish','publish_after_prepare')))
        except Exception as exc:
            _set(status="error", running=False, failure_count=STATE["failure_count"]+1, last_error=f"{type(exc).__name__}"[:100])
        # Rendering remains infrequent, but release completed videos promptly
        # when their independent channel slot becomes available.
        deadline = started + interval
        poll_seconds = max(30, int(os.getenv('MEME_PUBLISH_POLL_SECONDS', '120')))
        while remaining := deadline - time.time():
            if remaining <= 0:
                break
            time.sleep(min(poll_seconds, remaining))
            if time.time() >= deadline:
                break
            try:
                publication = publish_pending()
                if publication.get('uploaded') or publication.get('upload_failed'):
                    with LOCK:
                        snapshot = dict(STATE.get('last_result') or {})
                        snapshot['scheduled_publish'] = publication
                        STATE['last_result'] = snapshot
                        STATE['upload_count'] += int(publication.get('uploaded', 0))
                        STATE['failure_count'] += int(publication.get('upload_failed', 0))
            except Exception as exc:
                _set(last_error=type(exc).__name__, failure_count=STATE['failure_count'] + 1)


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        if self.path in {"/", "/health", "/healthz", "/ready", "/status"}:
            self.send_response(200 if self.path != '/ready' or _publish_ready() else 503)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self) -> None:
        if self.path == '/ready':
            ready = _publish_ready()
            self._reply(200 if ready else 503, {'status':'ready' if ready else 'persistence_required'})
        elif self.path in {'/','/health','/healthz'}:
            self._reply(200, {'status':'ok'})
        elif self.path == '/status':
            with LOCK: snapshot = dict(STATE)
            try:
                with PublishQueue(db_path(),'bamloop') as queue:
                    snapshot.update(queue.counts())
                    snapshot['next_publish_slot']=queue.next_slot()
                    snapshot['daily_ai_spend']=0.0
                    snapshot['daily_ai_budget']=float(os.getenv('BAMLOOP_DAILY_AI_BUDGET_USD','0'))
                    snapshot['ai_provider']=os.getenv('BAMLOOP_STORY_PROVIDER','local')
                    snapshot['youtube_credentials_ready']=credentials_ready()
                    snapshot['youtube_enabled']=os.getenv('MEME_YOUTUBE_ENABLED','false').casefold() in {'1','true','yes','on'}
                    snapshot['youtube_privacy_status']=os.getenv('MEME_YOUTUBE_PRIVACY_STATUS','private')
                    snapshot['db_persistence_ready']=persistent_render_path(db_path())
                    snapshot['direct_publish_enabled']=direct_publish_enabled()
                    snapshot['github_ledger_required']=ledger_required()
                    snapshot['github_ledger_ready']=ledger_ready() if ledger_required() else False
                    snapshot['publishing_ready']=credentials_ready() and publishing_storage_ready(db_path()) and (not ledger_required() or ledger_ready())
                    snapshot['persistence_blocked']=snapshot['youtube_enabled'] and not publishing_storage_ready(db_path())
            except Exception:
                snapshot['db_persistence_ready']=False
                snapshot['publishing_ready']=False
            self._reply(200,snapshot)
        else:
            self._reply(404, {'error':'not_found'})

    def log_message(self, format: str, *args: object) -> None:
        return


def _publish_ready() -> bool:
    """Worker health is separate from durable YouTube publishing readiness."""
    enabled = os.getenv('MEME_YOUTUBE_ENABLED','false').casefold() in {'1','true','yes','on'}
    return not enabled or (publishing_storage_ready(db_path()) and (not ledger_required() or ledger_ready()))


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    _set(status="idle")
    threading.Thread(target=worker, daemon=True, name="bamloop-worker").start()
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
