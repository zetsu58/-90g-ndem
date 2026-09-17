from __future__ import annotations

import os

from viral_futbol.config import Settings
from viral_futbol.service_v2 import run_once_v2
from viral_futbol.worker import AutonomousWorker
from viral_futbol.youtube_publisher import publish_ready
from viral_futbol.x_dedupe import XPublishedStore
from viral_futbol.x_newsroom import fetch_x_newsroom
from viral_futbol.x_pipeline import publish_verified_cluster
from viral_futbol.trend_pipeline import trend_gate


def _x_daily_limit() -> int:
    try:
        return max(0, int(os.getenv("X_DAILY_POST_LIMIT", "20")))
    except ValueError:
        return 20


def cycle() -> dict:
    settings = Settings()
    result = {"trend_gate": None, "x": {"verified": 0, "published": 0, "duplicates": 0, "budget_blocked": 0, "failed": 0}, "shorts": None, "youtube": None}

    try:
        result["trend_gate"] = trend_gate(settings)
    except Exception as exc:
        result["trend_gate"] = {"error": str(exc), "accepted": 0}
        print(f"ViralFutbol trend gate deferred: {exc}", flush=True)

    try:
        clusters = fetch_x_newsroom(settings)
        result["x"]["verified"] = len(clusters)
        limit = _x_daily_limit()
        accepted_titles = {item["title"] for item in (result.get("trend_gate") or {}).get("top", [])}
        with XPublishedStore(settings.db_path) as x_store:
            for cluster in clusters:
                title = cluster[0].title
                if accepted_titles and title not in accepted_titles:
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

    try:
        result["shorts"] = run_once_v2(settings)
    except Exception as exc:
        result["shorts"] = {"error": str(exc)}
        print(f"ViralFutbol Shorts V2 scan deferred: {exc}", flush=True)

    try:
        result["youtube"] = publish_ready(settings)
    except Exception as exc:
        result["youtube"] = {"error": str(exc)}
        print(f"ViralFutbol YouTube publisher deferred: {exc}", flush=True)

    return result


if __name__ == "__main__":
    print("ViralFutbol V2 autonomous worker + trend gate started", flush=True)
    AutonomousWorker(cycle).serve_forever()
