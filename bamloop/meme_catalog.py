"""Visually reviewed comedy beats, rather than keyword-matched stock footage."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

CONTRACT = "reviewed-reaction-meme-v1"


def reaction_mode():
    return os.getenv("BAMLOOP_CONTENT_MODE", "reaction_meme").casefold() == "reaction_meme"


def catalog():
    clips = json.loads(Path(__file__).with_name("meme_clips.json").read_text(encoding="utf-8"))
    for clip in clips:
        span = clip["end"] - clip["start"]
        if not (clip.get("reviewed_event") and 3 <= span <= 15 and
                0 < clip["punchline_at"] < span and 0 <= clip["reaction_at"] < span and
                len(clip.get("sha256", "")) == 64 and clip.get("license_url") and
                all(clip.get(k) for k in ("setup", "punchline", "reaction", "author", "source_page"))):
            raise ValueError("Invalid reviewed meme beat")
    return clips


def content_id(clip):
    # One actual clip = one durable identity, even if its caption is changed.
    return hashlib.sha256(("reaction-meme|" + clip["sha256"]).encode()).hexdigest()[:24]


def require_reviewed_meme(metadata):
    if not reaction_mode():
        return
    if metadata.get('meme_contract') == 'original-vehicle-simulation-v1':
        from .simulation import CONTRACT as SIM_CONTRACT, SCENARIOS, scenario_signature
        scenarios = {scenario['id']: scenario for scenario in SCENARIOS}
        scenario = scenarios.get(metadata.get('simulation_id'))
        enabled = os.getenv('BAMLOOP_SIMULATION_ENABLED', 'false').casefold() in {'1', 'true', 'yes', 'on'}
        if (not enabled or metadata.get('meme_contract') != SIM_CONTRACT or not scenario or
                metadata.get('simulation_signature') != scenario_signature(scenario) or
                metadata.get('content_format') != 'short'):
            raise ValueError('meme_content_unreviewed')
        return
    candidates = {clip["id"]: clip for clip in catalog()}
    clip = candidates.get(metadata.get("clip_id"))
    if (metadata.get("meme_contract") != CONTRACT or not clip or
            metadata.get("source_sha256") != clip["sha256"] or
            metadata.get("reviewed_event") != clip["reviewed_event"]):
        raise ValueError("meme_content_unreviewed")


def quarantine_legacy(queue):
    """Keep published/in-flight records intact; stale stock/story jobs cannot publish."""
    if not reaction_mode():
        return
    with queue.db:
        for row in queue.db.execute("SELECT content_id,metadata FROM publish_queue WHERE channel='bamloop' AND upload_state IN ('queued','failed')").fetchall():
            try:
                require_reviewed_meme(json.loads(row["metadata"]))
            except (ValueError, TypeError):
                queue.db.execute("UPDATE publish_queue SET upload_state='quality_blocked',last_error='meme_content_unreviewed' WHERE channel='bamloop' AND content_id=?", (row["content_id"],))

