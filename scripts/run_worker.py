from __future__ import annotations

from viral_futbol.config import Settings
from viral_futbol.service import run_scan
from viral_futbol.worker import AutonomousWorker
from viral_futbol.x_newsroom import fetch_x_newsroom
from viral_futbol.x_pipeline import publish_verified_cluster


def cycle() -> dict:
    settings = Settings()
    result = {"x": {"verified": 0, "published": 0, "failed": 0}, "shorts": None}

    # General Turkish news lane: politics, economy, daily life, world, tech, health.
    # It never waits for video rendering.
    try:
        clusters = fetch_x_newsroom(settings)
        result["x"]["verified"] = len(clusters)
        for cluster in clusters:
            publish_result = publish_verified_cluster(cluster, language="tr")
            if publish_result is None:
                continue
            if publish_result.ok:
                result["x"]["published"] += 1
            else:
                result["x"]["failed"] += 1
                print(f"ViralFutbol X publish failed: {publish_result.error}", flush=True)
    except Exception as exc:
        result["x"]["failed"] += 1
        print(f"ViralFutbol X newsroom deferred: {exc}", flush=True)

    # Separate lane: football-only Shorts.
    try:
        result["shorts"] = run_scan(settings)
    except Exception as exc:
        result["shorts"] = {"error": str(exc)}
        print(f"ViralFutbol Shorts scan deferred: {exc}", flush=True)

    return result


if __name__ == "__main__":
    print("ViralFutbol autonomous worker started", flush=True)
    AutonomousWorker(cycle).serve_forever()
