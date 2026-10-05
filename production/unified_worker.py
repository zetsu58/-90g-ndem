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
    result = {"publish": publish_pending(), "prepare": {"deferred": True}}
    # Unified mode runs this function, not bamloop.pipeline.cycle(). Keep the
    # meme analytics collector alive here as well, with bounded API frequency.
    with PublishQueue(path, 'bamloop') as queue:
        has_metrics = queue.db.execute("SELECT 1 FROM sqlite_master WHERE name='shorts_performance'").fetchone()
        last_metrics = queue.db.execute(
            "SELECT MAX(p.updated_at) FROM shorts_performance p JOIN publish_queue q "
            "ON p.story_id=q.content_id WHERE q.channel='bamloop' AND q.upload_state='published'"
        ).fetchone()[0] if has_metrics else None
        has_published = queue.db.execute(
            "SELECT 1 FROM publish_queue WHERE channel='bamloop' AND upload_state='published' LIMIT 1"
        ).fetchone()
    metrics_interval = max(3600, float(os.getenv('BAMLOOP_ANALYTICS_INTERVAL_SECONDS','10800')))
    if has_published and (last_metrics is None or now-last_metrics >= metrics_interval):
        try:
            from bamloop.performance import collect
            result['performance'] = collect(path)
        except Exception as exc:
            result['performance'] = {'ready':False,'error':type(exc).__name__}
    if not pending and (last is None or now - last >= interval):
        try:
            import gc
            gc.collect()
            result["prepare"] = prepare()
        except Exception as exc:
            result["prepare"] = {"error": type(exc).__name__}
        result["publish_after_prepare"] = publish_pending()
    return result
