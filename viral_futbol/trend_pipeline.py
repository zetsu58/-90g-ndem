from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from viral_futbol.x_newsroom import fetch_x_newsroom


@dataclass(frozen=True)
class TrendPick:
    title: str
    score: int
    sources: int
    reason: str


def _score(title: str, sources: int) -> int:
    text = title.casefold()
    score = min(35, sources * 12)
    hot = {
        "galatasaray": 18, "fenerbahçe": 18, "beşiktaş": 16,
        "transfer": 16, "şampiyonlar ligi": 15, "derbi": 18,
        "gol": 8, "sakat": 8, "imza": 12, "resmi": 12,
    }
    for token, points in hot.items():
        if token in text:
            score += points
    return min(100, score + 20)


def select_trends(settings) -> list[TrendPick]:
    minimum = max(0, min(100, int(os.getenv("VIRAL_TREND_MIN_SCORE", "58"))))
    picks: list[TrendPick] = []
    seen: set[str] = set()
    for cluster in fetch_x_newsroom(settings):
        if not cluster:
            continue
        title = cluster[0].title.strip()
        key = " ".join(title.casefold().split())
        if not title or key in seen:
            continue
        seen.add(key)
        score = _score(title, len(cluster))
        if score >= minimum:
            picks.append(TrendPick(title, score, len(cluster), "verified-cluster"))
    return sorted(picks, key=lambda item: item.score, reverse=True)


def trend_gate(settings) -> dict:
    picks = select_trends(settings)
    return {
        "minimum_score": int(os.getenv("VIRAL_TREND_MIN_SCORE", "58")),
        "accepted": len(picks),
        "top": [asdict(item) for item in picks[:10]],
    }
