from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .service import (
    Store,
    _fetch_queries,
    build_payload,
    news_editions,
    reconcile_jobs,
    submit,
    verified_clusters,
)
from .viral_engine import evaluate_cluster


def run_once_v2(settings) -> dict:
    """Run the existing pipeline with the Viral Engine V2 production gate."""
    with Store(settings.db_path) as store:
        reconciliation = (
            {"completed": 0, "failed": 0, "processing": 0, "unreachable": 0}
            if settings.dry_run
            else reconcile_jobs(store, settings)
        )
        diagnostics = {
            "fetched": 0,
            "recent": 0,
            "verified": 0,
            "viral_produce": 0,
            "viral_hold": 0,
            "viral_ignore": 0,
            "duplicates": 0,
            "submitted": 0,
            "submission_failed": 0,
            "deferred_capacity": 0,
            "deferred_retry": 0,
            "dry_run": settings.dry_run,
            "languages": {},
            "selected": [],
        }
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.max_age_minutes)
        available_slots = max(0, max(1, settings.max_inflight_tasks) - store.active_count())

        for language, country, queries in news_editions(settings):
            stories = _fetch_queries(
                queries,
                language=language,
                country=country,
                workers=settings.fetch_workers,
            )
            recent = [story for story in stories if story.published >= cutoff]
            clusters = verified_clusters(stories, settings)
            language_diagnostics = {
                "fetched": len(stories),
                "recent": len(recent),
                "verified": len(clusters),
                "viral_produce": 0,
                "viral_hold": 0,
                "viral_ignore": 0,
                "duplicates": 0,
                "submitted": 0,
                "submission_failed": 0,
                "deferred_capacity": 0,
                "deferred_retry": 0,
            }
            diagnostics["fetched"] += len(stories)
            diagnostics["recent"] += len(recent)
            diagnostics["verified"] += len(clusters)

            for cluster in clusters:
                decision = evaluate_cluster(cluster)
                gate = decision.score.decision
                diagnostics[f"viral_{gate}"] += 1
                language_diagnostics[f"viral_{gate}"] += 1
                if gate != "produce":
                    continue

                story_id = store.story_id(cluster, language)
                selected = {
                    "language": language,
                    "title": cluster[0].title,
                    "sources": sorted({story.publisher for story in cluster}),
                    "viral_score": decision.score.score,
                    "viral_reasons": list(decision.score.reasons),
                }

                if settings.dry_run:
                    submit(
                        build_payload(cluster, settings, language),
                        settings,
                        idempotency_key=f"viral-futbol:{story_id}",
                    )
                    diagnostics["submitted"] += 1
                    language_diagnostics["submitted"] += 1
                    selected["task_id"] = "dry-run"
                    diagnostics["selected"].append(selected)
                    continue

                if store.contains(story_id):
                    diagnostics["duplicates"] += 1
                    language_diagnostics["duplicates"] += 1
                    continue
                if available_slots <= 0:
                    diagnostics["deferred_capacity"] += 1
                    language_diagnostics["deferred_capacity"] += 1
                    continue
                if not store.reserve(
                    story_id,
                    language,
                    max_attempts=max(1, settings.max_task_attempts),
                    stale_seconds=max(60, settings.submission_stale_seconds),
                ):
                    diagnostics["deferred_retry"] += 1
                    language_diagnostics["deferred_retry"] += 1
                    continue

                try:
                    task_id = submit(
                        build_payload(cluster, settings, language),
                        settings,
                        idempotency_key=f"viral-futbol:{story_id}",
                    )
                    store.mark_submitted(story_id, task_id)
                    diagnostics["submitted"] += 1
                    language_diagnostics["submitted"] += 1
                    available_slots -= 1
                    selected["task_id"] = task_id
                    diagnostics["selected"].append(selected)
                except Exception as exc:
                    store.mark_failed(
                        story_id,
                        f"submission failed: {exc}",
                        settings.retry_delay_seconds,
                    )
                    diagnostics["submission_failed"] += 1
                    language_diagnostics["submission_failed"] += 1

            diagnostics["languages"][language] = language_diagnostics

        diagnostics.update(reconciliation)
        diagnostics["active"] = store.active_count()
        diagnostics["status_counts"] = store.status_counts()
        print("ViralFutbol V2 diagnostics: " + json.dumps(diagnostics, ensure_ascii=False), flush=True)
        return diagnostics
