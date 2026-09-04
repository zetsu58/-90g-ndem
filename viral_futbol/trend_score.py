from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class TrendSignals:
    source_count: int = 1
    official_source: bool = False
    transfer: bool = False
    breaking: bool = False
    social_velocity: float = 0.0
    published_at: datetime | None = None


@dataclass(frozen=True)
class TrendScore:
    score: int
    decision: str
    reasons: tuple[str, ...]


def score_trend(signals: TrendSignals, *, auto_threshold: int = 70, hold_threshold: int = 50) -> TrendScore:
    """Score a story without coupling the core service to a specific MCP provider."""
    score = 0
    reasons: list[str] = []

    if signals.transfer:
        score += 20
        reasons.append("transfer +20")
    if signals.breaking:
        score += 15
        reasons.append("breaking +15")
    if signals.official_source:
        score += 35
        reasons.append("official +35")
    if signals.source_count >= 2:
        score += 20
        reasons.append("multi-source +20")
    if signals.social_velocity >= 0.70:
        score += 15
        reasons.append("social velocity +15")

    if signals.published_at is not None:
        now = datetime.now(timezone.utc)
        published = signals.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_minutes = max(0.0, (now - published).total_seconds() / 60)
        if age_minutes <= 15:
            score += 10
            reasons.append("fresh <=15m +10")
        elif age_minutes <= 45:
            score += 5
            reasons.append("fresh <=45m +5")

    score = min(100, score)
    decision = "produce" if score >= auto_threshold else "hold" if score >= hold_threshold else "ignore"
    return TrendScore(score=score, decision=decision, reasons=tuple(reasons))
