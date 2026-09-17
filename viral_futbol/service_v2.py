from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

from .lite_video import render_lite_video
from .media_engine import build_media_plan, material_terms
from .retention_engine import build_retention_plan, retention_instruction
from .service import Store, _fetch_queries, build_payload, news_editions, reconcile_jobs, submit, verified_clusters
from .shorts_script import build_script_prompt
from .viral_engine import evaluate_cluster
from .visual_quality import build_visual_quality_plan, prioritized_terms
from .youtube_publisher import remember_manifest
from .content_strategy import build_content_strategy


def _shorts_min_score() -> int:
    try:
        return max(0, min(100, int(os.getenv("VIRAL_TREND_MIN_SCORE", "58"))))
    except ValueError:
        return 58


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
    payload["custom_system_prompt"] = "Sen Viral Futbol'un kıdemli Türkçe Shorts editörüsün. Yalnızca doğrulanmış girdileri kullan. İlk iki saniye izleyiciyi yakalamalı; clickbait uğruna gerçeği bozma. Kısa cümleler ve yüksek tempo kullan. Yalnızca doğal, tek parça seslendirme metni döndür. İçerik öncelik puanı: %d/100." % viral_score
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
    with Store(settings.db_path) as store:
        reconciliation = {"completed": 0, "failed": 0, "processing": 0, "unreachable": 0} if settings.dry_run else reconcile_jobs(store, settings)
        diagnostics = {"fetched": 0, "recent": 0, "verified": 0, "viral_produce": 0, "viral_hold": 0, "viral_ignore": 0, "below_trend_gate": 0, "duplicates": 0, "previewed": 0, "submitted": 0, "generated_lite": 0, "submission_failed": 0, "deferred_capacity": 0, "deferred_retry": 0, "dry_run": settings.dry_run, "trend_min_score": minimum_score, "languages": {}, "selected": []}
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.max_age_minutes)
        available_slots = min(1, max(0, max(1, settings.max_inflight_tasks) - store.active_count()))
        for language, country, queries in news_editions(settings):
            stories = _fetch_queries(queries, language=language, country=country, workers=settings.fetch_workers)
            recent = [s for s in stories if s.published >= cutoff]
            unique_recent = {s.url or s.title: s for s in recent}
            clusters = [[s] for s in sorted(unique_recent.values(), key=lambda item: item.published, reverse=True)]
            ld = {"fetched": len(stories), "recent": len(recent), "verified": len(clusters), "viral_produce": 0, "viral_hold": 0, "viral_ignore": 0, "below_trend_gate": 0, "duplicates": 0, "previewed": 0, "submitted": 0, "generated_lite": 0, "submission_failed": 0, "deferred_capacity": 0, "deferred_retry": 0}
            diagnostics["fetched"] += len(stories); diagnostics["recent"] += len(recent); diagnostics["verified"] += len(clusters)
            for cluster in clusters:
                decision = evaluate_cluster(cluster)
                score = decision.score.score
                if language == "tr" and score < minimum_score:
                    diagnostics["viral_hold"] += 1; ld["viral_hold"] += 1
                    diagnostics["below_trend_gate"] += 1; ld["below_trend_gate"] += 1
                    continue
                diagnostics["viral_produce"] += 1; ld["viral_produce"] += 1
                story_id = store.story_id(cluster, language)
                strategy = build_content_strategy(settings.db_path, cluster[0].title) if language == "tr" else None
                payload = build_v2_payload(cluster, settings, language, score)
                if strategy and strategy.confidence in {"medium", "high"}:
                    payload["custom_system_prompt"] += f" Öğrenilmiş açılış biçimi: {strategy.hook}. Bunu doğal uygula; doğrulanmış bilgilerin dışına çıkma."
                selected = {"language": language, "title": cluster[0].title, "sources": sorted({s.publisher for s in cluster}), "viral_score": score, "viral_reasons": list(decision.score.reasons), "trend_gate": "accepted", "script_engine": "shorts-v2" if language == "tr" else "legacy-en", "video_subject": payload.get("video_subject", ""), "clip_duration": payload.get("video_clip_duration"), "subtitle_font_size": payload.get("font_size"), "strategy": strategy.as_dict() if strategy else None}
                remember_manifest(settings.db_path, story_id, cluster[0].title, language, sorted({s.publisher for s in cluster}))
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
                        store.mark_complete(story_id, video_path.resolve().as_uri()); diagnostics["generated_lite"] += 1; ld["generated_lite"] += 1; available_slots -= 1; selected["task_id"] = f"lite:{story_id}"
                    else:
                        task_id = submit(payload, settings, idempotency_key=f"viral-futbol:{story_id}")
                        store.mark_submitted(story_id, task_id); diagnostics["submitted"] += 1; ld["submitted"] += 1; available_slots -= 1; selected["task_id"] = task_id
                    diagnostics["selected"].append(selected)
                except Exception as exc:
                    store.mark_failed(story_id, f"submission failed: {exc}", settings.retry_delay_seconds); diagnostics["submission_failed"] += 1; ld["submission_failed"] += 1
            diagnostics["languages"][language] = ld
        diagnostics.update(reconciliation); diagnostics["active"] = store.active_count(); diagnostics["status_counts"] = store.status_counts()
        print("ViralFutbol V2 diagnostics: " + json.dumps(diagnostics, ensure_ascii=False), flush=True)
        return diagnostics
