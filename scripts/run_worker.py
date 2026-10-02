from __future__ import annotations

import os

from viral_futbol.config import Settings
from viral_futbol.service_v2 import run_once_v2
from viral_futbol.worker import AutonomousWorker
from viral_futbol.youtube_publisher import publish_ready, YouTubeConfig, _refresh_credentials
from viral_futbol.youtube_performance import collect_youtube_performance
from viral_futbol.x_dedupe import XPublishedStore
from viral_futbol.x_newsroom import fetch_x_newsroom
from viral_futbol.x_pipeline import publish_verified_cluster
from viral_futbol.trend_pipeline import trend_gate
from production.format_scheduler import decide as decide_formats
from production.longform_runtime import last_activity as last_longform_activity, produce_once as produce_longform
from production.youtube_auth import channel_preflight


def _x_daily_limit() -> int:
    try:
        return max(0, int(os.getenv("X_DAILY_POST_LIMIT", "20")))
    except ValueError:
        return 20


def cycle(progress=None) -> dict:
    def stage(name: str) -> None:
        print(f"ViralFutbol cycle stage: {name}", flush=True)
        if progress:
            progress(name)
    settings = Settings()
    stage("trend_gate")
    longform_enabled=os.getenv('VIRAL_LONGFORM_ENABLED',os.getenv('LONGFORM_ENABLED','false')).casefold() in {'1','true','yes','on'}
    try: longform_interval=float(os.getenv('VIRAL_LONGFORM_INTERVAL_HOURS',os.getenv('LONGFORM_INTERVAL_HOURS','24')))
    except ValueError: longform_interval=24.0
    format_decision = decide_formats(last_longform_at=last_longform_activity(settings.db_path,'viral_futbol'),longform_enabled=longform_enabled,interval_hours=longform_interval)
    result = {"formats": {"shorts": format_decision.shorts, "longform": format_decision.longform, "reason": format_decision.reason}, "trend_gate": None, "x": {"verified": 0, "published": 0, "duplicates": 0, "budget_blocked": 0, "gate_blocked": 0, "failed": 0}, "shorts": None, "longform": None, "youtube": None, "performance": None}

    try:
        result["trend_gate"] = trend_gate(settings)
    except Exception as exc:
        result["trend_gate"] = {"error": str(exc), "accepted": 0, "top": []}
        print(f"ViralFutbol trend gate deferred: {exc}", flush=True)

    gate_result = result.get("trend_gate") or {}
    gate_ok = "error" not in gate_result
    accepted_titles = {str(item.get("title") or "").strip() for item in gate_result.get("top", []) if str(item.get("title") or "").strip()}

    stage("x_newsroom")
    if os.getenv("X_PUBLISH_ENABLED", "false").casefold() not in {"1", "true", "yes", "on"}:
        result["x"]["disabled"] = True
    else:
      try:
        clusters = fetch_x_newsroom(settings)
        result["x"]["verified"] = len(clusters)
        limit = _x_daily_limit()
        with XPublishedStore(settings.db_path) as x_store:
            for cluster in clusters:
                title = cluster[0].title
                # Fail closed: an unavailable gate or a successful gate with zero
                # accepted titles must never turn into "publish everything".
                if not gate_ok or title not in accepted_titles:
                    result["x"]["gate_blocked"] += 1
                    continue
                if x_store.contains(title):
                    result["x"]["duplicates"] += 1
                    continue
                if not x_store.reserve(title, limit):
                    result["x"]["budget_blocked"] += 1
                    continue
                publish_result = publish_verified_cluster(cluster, language="tr")
                if publish_result is None:
                    x_store.release(title)
                    continue
                if publish_result.ok:
                    x_store.mark(title, publish_result.external_id)
                    result["x"]["published"] += 1
                else:
                    x_store.release(title)
                    result["x"]["failed"] += 1
                    print(f"ViralFutbol X publish failed: {publish_result.error}", flush=True)
      except Exception as exc:
        result["x"]["failed"] += 1
        print(f"ViralFutbol X newsroom deferred: {exc}", flush=True)

    stage("shorts_scan")
    try:
        result["shorts"] = run_once_v2(settings, progress=lambda name: stage(f"shorts:{name}"))
    except Exception as exc:
        result["shorts"] = {"error": str(exc)}
        print(f"ViralFutbol Shorts V2 scan deferred: {exc}", flush=True)

    shorts_ok = isinstance(result.get("shorts"), dict) and "error" not in (result.get("shorts") or {})
    stage("longform")
    if not shorts_ok:
        result["longform"] = {"deferred": True, "reason": "shorts_scan_failed"}
    elif format_decision.longform:
        config=YouTubeConfig.from_env()
        if not config.ready:
            result["longform"] = {"deferred": True, "reason": "youtube_credentials_not_ready"}
        else:
            try:
                credentials=_refresh_credentials(config)
                channel_preflight(credentials,os.getenv("YOUTUBE_EXPECTED_CHANNEL_ID","").strip())
                result["longform"] = produce_longform(
                    channel="viral_futbol",
                    db_path=settings.db_path,
                    output_dir=os.getenv("VIRAL_LONGFORM_OUTPUT_DIR","storage/viral_longform"),
                    voice=settings.voice_name,
                )
            except Exception as exc:
                result["longform"] = {"deferred": True, "error": type(exc).__name__, "reason": "longform_preflight_or_production_failed"}
                print(f"ViralFutbol long-form deferred: {type(exc).__name__}", flush=True)
    else:
        result["longform"] = {"deferred": True, "reason": format_decision.reason}

    # Upload only after this cycle's Shorts scan completed cleanly. Existing
    # complete jobs remain queued instead of being published during a degraded run.
    stage("youtube_publish")
    if shorts_ok:
        try:
            result["youtube"] = publish_ready(settings)
        except Exception as exc:
            result["youtube"] = {"error": str(exc)}
            print(f"ViralFutbol YouTube publisher deferred: {exc}", flush=True)
    else:
        result["youtube"] = {"deferred": True, "reason": "shorts_scan_failed"}

    # Performance collection is deliberately non-blocking: analytics/OAuth trouble
    # must never stop news scanning, rendering, or publishing.
    stage("performance")
    try:
        result["performance"] = collect_youtube_performance(settings.db_path)
    except Exception as exc:
        result["performance"] = {"error": str(exc), "deferred": True}
        print(f"ViralFutbol performance collector deferred: {exc}", flush=True)

    stage("done")
    return result


if __name__ == "__main__":
    print("ViralFutbol V2 autonomous worker + fail-closed quality gates started", flush=True)
    AutonomousWorker(cycle).serve_forever()
