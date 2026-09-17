from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo


HOOKS = {
    "breaking": ("son dakika", "bir saniye", "şimdi değişti"),
    "question": ("sence", "neden", "ne oldu", "kim"),
    "official": ("resmi", "açıklandı", "imza"),
    "conflict": ("kriz", "şok", "gerilim", "rest"),
}


def hook_type(title: str) -> str:
    text = title.casefold()
    for kind, tokens in HOOKS.items():
        if any(token in text for token in tokens):
            return kind
    return "direct"


def hour_bucket(timestamp: float) -> str:
    timezone_name = os.getenv("CHANNEL_TIMEZONE", "Europe/Istanbul").strip() or "Europe/Istanbul"\n    try:\n        zone = ZoneInfo(timezone_name)\n    except Exception:\n        zone = ZoneInfo("Europe/Istanbul")\n    hour = datetime.fromtimestamp(timestamp, tz=zone).hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 23:
        return "evening"
    return "night"


def _shrunken(values: list[float], minimum: int = 3) -> tuple[float, int]:
    if len(values) < minimum:
        return 50.0, len(values)
    avg = sum(values) / len(values)
    confidence = min(1.0, len(values) / 10.0)
    return 50.0 + (avg - 50.0) * confidence, len(values)


def creative_report(db_path: str, limit: int = 200) -> dict:
    db = sqlite3.connect(db_path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT m.title, p.score, y.updated_at, c.hook_variant\n            FROM shorts_performance p\n            JOIN youtube_manifests m ON m.story_id=p.story_id\n            JOIN youtube_publications y ON y.story_id=p.story_id\n            LEFT JOIN shorts_creatives c ON c.story_id=p.story_id
            WHERE y.status='published'
            ORDER BY p.updated_at DESC LIMIT ?
            """,
            (max(20, limit),),
        ).fetchall()
    except sqlite3.OperationalError:
        return {"hooks": {}, "hours": {}, "samples": 0}
    finally:
        db.close()

    hooks = defaultdict(list)
    hours = defaultdict(list)
    for row in rows:
        score = float(row["score"])
        actual_hook = str(row["hook_variant"] or "").strip()\n        hooks[actual_hook or hook_type(str(row["title"]))].append(score)
        hours[hour_bucket(float(row["updated_at"]))].append(score)

    hook_report = {}
    for key, values in hooks.items():
        score, samples = _shrunken(values)
        hook_report[key] = {"score": round(score, 2), "samples": samples}

    hour_report = {}
    for key, values in hours.items():
        score, samples = _shrunken(values)
        hour_report[key] = {"score": round(score, 2), "samples": samples}

    return {"hooks": hook_report, "hours": hour_report, "samples": len(rows)}


def recommended_hook(db_path: str) -> str | None:
    report = creative_report(db_path)
    eligible = [(data["score"], key) for key, data in report["hooks"].items() if data["samples"] >= 3]
    return max(eligible)[1] if eligible else None


def recommended_time_bucket(db_path: str) -> str | None:
    report = creative_report(db_path)
    eligible = [(data["score"], key) for key, data in report["hours"].items() if data["samples"] >= 3]
    return max(eligible)[1] if eligible else None
