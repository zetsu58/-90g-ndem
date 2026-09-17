from __future__ import annotations

import re
import sqlite3
from collections import defaultdict


TOPICS = {
    "galatasaray": ("galatasaray", "gs"),
    "fenerbahce": ("fenerbahçe", "fenerbahce", "fb"),
    "besiktas": ("beşiktaş", "besiktas", "bjk"),
    "trabzonspor": ("trabzonspor",),
    "transfer": ("transfer", "imza", "bonservis", "kiralık"),
    "derbi": ("derbi",),
    "champions_league": ("şampiyonlar ligi", "champions league"),
    "injury": ("sakat", "sakatlık"),
    "goal": ("gol",),
}


def topics_for(title: str) -> set[str]:
    text = " " + re.sub(r"\s+", " ", title.casefold()).strip() + " "
    found = set()
    for topic, aliases in TOPICS.items():
        for alias in aliases:
            if len(alias) <= 3:
                if f" {alias} " in text:
                    found.add(topic)
                    break
            elif alias in text:
                found.add(topic)
                break
    return found


def topic_boost(db_path: str, title: str, sample_limit: int = 80) -> tuple[float, list[str]]:
    current = topics_for(title)
    if not current:
        return 0.0, []

    db = sqlite3.connect(db_path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT m.title, p.score
            FROM shorts_performance p
            JOIN youtube_manifests m ON m.story_id=p.story_id
            ORDER BY p.updated_at DESC LIMIT ?
            """,
            (max(10, sample_limit),),
        ).fetchall()
    except sqlite3.OperationalError:
        return 0.0, []
    finally:
        db.close()

    scores = defaultdict(list)
    for row in rows:
        for topic in topics_for(str(row["title"])):
            scores[topic].append(float(row["score"]))

    weighted = []
    evidence = []
    for topic in sorted(current):
        values = scores.get(topic, [])
        if len(values) < 2:
            continue
        # Shrink small samples toward neutral 50 to avoid overfitting.
        avg = sum(values) / len(values)
        confidence = min(1.0, len(values) / 8.0)
        adjusted = 50.0 + (avg - 50.0) * confidence
        weighted.append(adjusted)
        evidence.append(f"{topic}:{len(values)}")

    if not weighted:
        return 0.0, []
    mean = sum(weighted) / len(weighted)
    boost = max(-6.0, min(10.0, (mean - 50.0) * 0.20))
    return round(boost, 2), evidence
