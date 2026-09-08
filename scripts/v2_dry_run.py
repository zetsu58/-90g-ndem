from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

# Force safe mode before Settings is imported.
os.environ["NEWS_DRY_RUN"] = "true"
os.environ.setdefault("NEWS_LANGUAGES", "tr")

from viral_futbol.config import Settings
from viral_futbol.media_engine import build_media_plan, material_terms
from viral_futbol.service import _fetch_queries, news_editions, verified_clusters
from viral_futbol.service_v2 import build_v2_payload
from viral_futbol.viral_engine import evaluate_cluster


def main() -> int:
    settings = Settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.max_age_minutes)
    report: list[dict] = []

    for language, country, queries in news_editions(settings):
        if language != "tr":
            continue
        stories = _fetch_queries(queries, language=language, country=country, workers=settings.fetch_workers)
        clusters = verified_clusters(stories, settings)
        for cluster in clusters:
            decision = evaluate_cluster(cluster)
            facts = [f"{s.publisher}: {s.title}" for s in cluster[:5]]
            media = build_media_plan(cluster[0].title, facts)
            item = {
                "title": cluster[0].title,
                "published": max(s.published for s in cluster).isoformat(),
                "recent": max(s.published for s in cluster) >= cutoff,
                "sources": sorted({s.publisher for s in cluster}),
                "viral_score": decision.score.score,
                "decision": decision.score.decision,
                "reasons": list(decision.score.reasons),
                "media_context": media.context,
                "media_terms": material_terms(media),
            }
            if decision.score.decision == "produce":
                payload = build_v2_payload(cluster, settings, language, decision.score.score)
                item["script_prompt"] = payload.get("video_script_prompt", "")
                item["final_video_terms"] = payload.get("video_terms", [])
                item["render_settings"] = {
                    "aspect": payload.get("video_aspect"),
                    "clip_duration": payload.get("video_clip_duration"),
                    "subtitle": payload.get("subtitle_enabled"),
                    "font_size": payload.get("font_size"),
                    "bgm_volume": payload.get("bgm_volume"),
                }
            report.append(item)

    report.sort(key=lambda x: x["viral_score"], reverse=True)
    print(json.dumps({"dry_run": True, "count": len(report), "stories": report[:10]}, ensure_ascii=False, indent=2))
    print("\nSAFE DRY-RUN: MPT submit çağrısı yapılmadı, video render edilmedi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
