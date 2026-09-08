from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class TrendSignals:
    source_count: int = 1
    official_source: bool = False
    transfer: bool = False
    breaking: bool = False
    injury: bool = False
    controversy: bool = False
    derby_or_big_match: bool = False
    major_team_or_player: bool = False
    social_velocity: float = 0.0
    published_at: datetime | None = None


@dataclass(frozen=True)
class TrendScore:
    score: int
    decision: str
    reasons: tuple[str, ...]


def score_trend(signals: TrendSignals, *, auto_threshold: int = 75, hold_threshold: int = 55) -> TrendScore:
    """Score a football story for short-form production.

    V2 combines reliability, freshness and audience-interest signals. The score
    is intentionally deterministic so it can be tested and later calibrated
    against YouTube analytics.
    """
    score = 0
    reasons: list[str] = []

    if signals.official_source:
        score += 25
        reasons.append("official +25")
    if signals.source_count >= 2:
        score += 15
        reasons.append("multi-source +15")

    if signals.transfer:
        score += 15
        reasons.append("transfer +15")
    if signals.breaking:
        score += 15
        reasons.append("breaking +15")
    if signals.injury:
        score += 10
        reasons.append("injury +10")
    if signals.controversy:
        score += 10
        reasons.append("controversy +10")
    if signals.derby_or_big_match:
        score += 10
        reasons.append("big-match +10")
    if signals.major_team_or_player:
        score += 10
        reasons.append("major entity +10")

    velocity = max(0.0, min(1.0, signals.social_velocity))
    if velocity >= 0.85:
        score += 15
        reasons.append("social velocity >=.85 +15")
    elif velocity >= 0.60:
        score += 8
        reasons.append("social velocity >=.60 +8")

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
            score += 6
            reasons.append("fresh <=45m +6")
        elif age_minutes <= 120:
            score += 3
            reasons.append("fresh <=120m +3")

    score = min(100, score)
    decision = "produce" if score >= auto_threshold else "hold" if score >= hold_threshold else "ignore"
    return TrendScore(score=score, decision=decision, reasons=tuple(reasons))
