"""Run BAMLOOP serially inside ViralFutbol's existing cycle lock."""
import os
import time

from production.publishing_policy import unified_channel


def run_bamloop():
    if not unified_channel():
        return {"disabled": True}
    from bamloop.pipeline import db_path, prepare, publish_pending
    from production.queue import PublishQueue
    path = db_path()
    now = time.time()
    interval = max(60, float(os.getenv("MEME_INTERVAL_SECONDS", "10800")))
    with PublishQueue(path, "bamloop") as queue:
        from bamloop.meme_catalog import quarantine_legacy
        quarantine_legacy(queue)
        last = queue.db.execute("SELECT MAX(created_at) FROM publish_queue WHERE channel='bamloop'").fetchone()[0]
        pending = queue.db.execute("SELECT COUNT(*) FROM publish_queue WHERE channel='bamloop' AND upload_state IN ('queued','failed','uploading','uncertain') AND content_type!='video'").fetchone()[0]
    result = {"publish": publish_pending(), "prepare": {"deferred": True, "reason": "pending_queue" if pending else "generation_interval"}}
    if not pending and (last is None or now - last >= interval):
        try:
            import gc
            gc.collect()
            result["prepare"] = prepare()
        except Exception as exc:
            result["prepare"] = {"error": type(exc).__name__}
        result["publish_after_prepare"] = publish_pending()
    print("BAMLOOP cycle: " + str({key: {field: value for field, value in (part or {}).items()
                                    if field in {'queued', 'uploaded', 'video_id', 'reason', 'error', 'scheduled',
                                                 'ready', 'quality_blocked', 'ledger_blocked', 'upload_error_type'}}
                                    for key, part in result.items()}), flush=True)
    return result

