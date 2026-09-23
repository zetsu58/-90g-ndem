from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from dataclasses import replace

from .lite_video import render_lite_video
from .media_engine import build_media_plan, material_terms
from .retention_engine import build_retention_plan, retention_instruction
from .service import Store, _fetch_queries, build_payload, news_editions, reconcile_jobs, submit, verified_clusters
from .shorts_script import build_script_prompt
from .viral_engine import evaluate_cluster
from .visual_quality import build_visual_quality_plan, prioritized_terms
from .youtube_publisher import remember_manifest
from .content_strategy import build_content_strategy
from .source_intelligence import confidence_gate
from .scene_manifest import SceneManifestStore
from .scene_learning import recommended_scene_creative
from .service import publisher_family
from production.github_ledger import GitHubLedger, required as ledger_required, ready as ledger_ready


def _shorts_min_score() -> int:
    try:
        return max(0, min(100, int(os.getenv("VIRAL_TREND_MIN_SCORE", "42"))))
    except ValueError:
        return 42


def _effective_trend_gate(clusters, minimum_score: int) -> int:
    """Publish the best trustworthy fresh report when a quiet news cycle has no trend hit."""
    eligible = [cluster for cluster in clusters if confidence_gate(cluster, publisher_family)[0]]
    if not eligible:
        return minimum_score
    return min(minimum_score, max(evaluate_cluster(cluster).score.score for cluster in eligible))


def build_v2_payload(cluster, settings, language: str, viral_score: int) -> dict:
    payload = build_payload(cluster, settings, language)
    if language != "tr":
        return payload
    facts = [f"{s.publisher}: {s.title}" for s in cluster[:5]]
    media_plan = build_media_plan(cluster[0].title, facts)
    visual_plan = build_visual_quality_plan(media_plan.entities, media_plan.context)
    retention = build_retention_plan(viral_score)
    media_terms = prioritized_terms(material_terms(media_plan), visual_plan)
    payload["video_script_prompt"] = build_script_prompt(title=cluster[0].title, facts=facts, target_seconds=40) + "\n\nRETENTION:\n" + retention_instruction(retention)
    payload["custom_system_prompt"] = "Sen Viral Futbol'un kıdemli Türkçe Shorts editörüsün. Yalnızca verilen haberlerdeki olguları kullan. Tek kaynaklı iddiaları kesinleşmiş olay gibi sunma. İlk iki saniye izleyiciyi yakalamalı; clickbait uğruna gerçeği bozma. Kısa cümleler ve yüksek tempo kullan. Yalnızca doğal, tek parça seslendirme metni döndür. İçerik öncelik puanı: %d/100." % viral_score
    if media_terms:
        payload["video_subject"] = f"{cluster[0].title} | " + ", ".join(media_terms[:6])
    payload["match_materials_to_script"] = True
    payload["video_clip_duration"] = visual_plan.clip_duration
    payload["video_transition_mode"] = visual_plan.transition_mode
    payload["subtitle_enabled"] = True
    payload["subtitle_position"] = retention.subtitle_position
    payload["font_size"] = retention.font_size
    payload["stroke_width"] = retention.stroke_width
    return payload


def run_once_v2(settings) -> dict:
    minimum_score = _shorts_min_score()
    if ledger_required() and not ledger_ready():
        return {"ledger_blocked": True, "reason": "github_ledger_token_missing", "fetched": 0, "selected": []}
    ledger = GitHubLedger() if ledger_required() else None
    with Store(settings.db_path) as store:
        reconciliation = {"completed": 0, "failed": 0, "processing": 0, "unreachable": 0} if settings.dry_run else reconcile_jobs(store, settings)
        diagnostics = {"fetched": 0, "recent": 0, "clustered": 0, "verified": 0, "rejected_source": 0, "rejected_conflict": 0, "queued": 0, "rendered": 0, "quality_blocked": 0, "uploaded": 0, "upload_failed": 0, "viral_produce": 0, "viral_hold": 0, "viral_ignore": 0, "below_trend_gate": 0, "duplicates": 0, "previewed": 0, "submitted": 0, "generated_lite": 0, "submission_failed": 0, "deferred_capacity": 0, "deferred_retry": 0, "dry_run": settings.dry_run, "trend_min_score": minimum_score, "languages": {}, "selected": []}
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.max_age_minutes)
        available_slots = min(1, max(0, max(1, settings.max_inflight_tasks) - store.active_count()))
        for language, country, queries in news_editions(settings):
            stories = _fetch_queries(queries, language=language, country=country, workers=settings.fetch_workers)
            recent = [s for s in stories if s.published >= cutoff]
            unique_recent = {s.url or s.title: s for s in recent}
            # Cluster all fresh candidates; confidence_gate below decides whether a
            # single reputable report is publishable. NEWS_MIN_SOURCES must
            # not discard it before that decision is made.
            clusters = verified_clusters(list(unique_recent.values()), replace(settings, min_sources=1))
            effective_gate = _effective_trend_gate(clusters, minimum_score) if language == 'tr' else minimum_score
            clusters.sort(key=lambda cluster: evaluate_cluster(cluster).score.score, reverse=True)
            diagnostics["clustered"] += len(clusters)
            ld = {"fetched": len(stories), "recent": len(recent), "verified": len(clusters), "viral_produce": 0, "viral_hold": 0, "viral_ignore": 0, "below_trend_gate": 0, "duplicates": 0, "previewed": 0, "submitted": 0, "generated_lite": 0, "submission_failed": 0, "deferred_capacity": 0, "deferred_retry": 0}
            diagnostics["fetched"] += len(stories); diagnostics["recent"] += len(recent); diagnostics["verified"] += len(clusters)
            for cluster in clusters:
                allowed, reason, _ = confidence_gate(cluster, publisher_family)
                if not allowed:
                    diagnostics['rejected_conflict' if reason == 'conflict' else 'rejected_source'] += 1
                    continue
                decision = evaluate_cluster(cluster)
                score = decision.score.score
                if language == "tr" and score < effective_gate:
                    diagnostics["viral_hold"] += 1; ld["viral_hold"] += 1
                    diagnostics["below_trend_gate"] += 1; ld["below_trend_gate"] += 1
                    continue
                diagnostics["viral_produce"] += 1; ld["viral_produce"] += 1
                if language == 'tr' and score < minimum_score:
                    diagnostics['trend_fallback'] = diagnostics.get('trend_fallback', 0) + 1
                story_id = store.story_id(cluster, language)
                if ledger and ledger.exists('viral_futbol',story_id):
                    diagnostics["duplicates"] += 1; ld["duplicates"] += 1; continue
                strategy = build_content_strategy(settings.db_path, cluster[0].title) if language == "tr" else None
                scene_advice = recommended_scene_creative(settings.db_path) if language == "tr" else None
                payload = build_v2_payload(cluster, settings, language, score)
                if strategy and strategy.confidence in {"medium", "high"}:
                    payload["custom_system_prompt"] += f" Öğrenilmiş açılış biçimi: {strategy.hook}. Bunu doğal uygula; doğrulanmış bilgilerin dışına çıkma."
                if scene_advice:
                    payload["learned_scene_creative"] = scene_advice.as_dict()
                selected = {"language": language, "title": cluster[0].title, "sources": sorted({s.publisher for s in cluster}), "viral_score": score, "viral_reasons": list(decision.score.reasons), "trend_gate": "accepted", "script_engine": "shorts-v2" if language == "tr" else "legacy-en", "video_subject": payload.get("video_subject", ""), "clip_duration": payload.get("video_clip_duration"), "subtitle_font_size": payload.get("font_size"), "strategy": strategy.as_dict() if strategy else None, "scene_advice": scene_advice.as_dict() if scene_advice else None}
                remember_manifest(settings.db_path, story_id, cluster[0].title, language, sorted({s.publisher for s in cluster}))
                if language == "tr":
                    with SceneManifestStore(settings.db_path) as scene_store:
                        scenes = scene_store.plan(story_id, cluster[0].title, target_seconds=24.0)
                    selected["scene_manifest"] = {"count": len(scenes), "repairable": True}
                if settings.dry_run:
                    submit(payload, settings, idempotency_key=f"viral-futbol:{story_id}")
                    diagnostics["previewed"] += 1; ld["previewed"] += 1; selected["task_id"] = "dry-run"; diagnostics["selected"].append(selected); continue
                if store.contains(story_id):
                    diagnostics["duplicates"] += 1; ld["duplicates"] += 1; continue
                if available_slots <= 0:
                    diagnostics["deferred_capacity"] += 1; ld["deferred_capacity"] += 1; continue
                if not store.reserve(story_id, language, max_attempts=max(1, settings.max_task_attempts), stale_seconds=max(60, settings.submission_stale_seconds)):
                    diagnostics["deferred_retry"] += 1; ld["deferred_retry"] += 1; continue
                try:
                    if settings.video_engine == "lite":
                        video_path = render_lite_video(story_id=story_id, title=cluster[0].title, sources=sorted({s.publisher for s in cluster}), facts=[s.title for s in cluster[:5]], language=language, voice_name=settings.voice_name if language == "tr" else settings.english_voice_name, output_dir=settings.lite_video_dir)
                        store.mark_complete(story_id, video_path.resolve().as_uri()); diagnostics["rendered"] += 1; diagnostics["queued"] += 1; diagnostics["generated_lite"] += 1; ld["generated_lite"] += 1; available_slots -= 1; selected["task_id"] = f"lite:{story_id}"
                    else:
                        task_id = submit(payload, settings, idempotency_key=f"viral-futbol:{story_id}")
                        store.mark_submitted(story_id, task_id); diagnostics["submitted"] += 1; ld["submitted"] += 1; available_slots -= 1; selected["task_id"] = task_id
                    diagnostics["selected"].append(selected)
                except Exception as exc:
                    # Keep status useful without leaking URLs, tokens, or API responses.
                    diagnostics["last_render_error_type"] = type(exc).__name__
                    store.mark_failed(story_id, f"submission failed: {type(exc).__name__}", settings.retry_delay_seconds); diagnostics["submission_failed"] += 1; ld["submission_failed"] += 1
            diagnostics["languages"][language] = ld
        diagnostics.update(reconciliation); diagnostics["active"] = store.active_count(); diagnostics["status_counts"] = store.status_counts()
        print("ViralFutbol V2 diagnostics: " + json.dumps(diagnostics, ensure_ascii=False), flush=True)
        return diagnostics
