from __future__ import annotations

from dataclasses import dataclass
import re

from .trend_score import TrendScore, TrendSignals, score_trend


@dataclass(frozen=True)
class ViralDecision:
    score: TrendScore
    signals: TrendSignals


TRANSFER_WORDS = ("transfer", "bonservis", "kiralık", "imza", "görüşme")
BREAKING_WORDS = ("son dakika", "açıkladı", "resmi", "resmen", "kap")
INJURY_WORDS = ("sakat", "sakatlık", "ameliyat", "tedavi", "MR")
CONTROVERSY_WORDS = ("kriz", "kavga", "ceza", "gerilim", "tartışma", "istifa")
BIG_MATCH_WORDS = ("derbi", "final", "şampiyonlar ligi", "avrupa ligi")
MAJOR_ENTITIES = (
    "galatasaray", "fenerbahçe", "beşiktaş", "trabzonspor",
    "real madrid", "barcelona", "liverpool", "manchester city",
    "bayern", "psg", "juventus", "inter", "milan",
    "osimhen", "icardi", "salah", "mbappe", "haaland", "yamal",
)


def _contains(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(word.casefold() in lowered for word in words)


def evaluate_cluster(cluster, *, social_velocity: float = 0.0) -> ViralDecision:
    """Turn an already corroborated news cluster into a V2 production decision."""
    text = " ".join(story.title for story in cluster)
    publishers = {getattr(story, "publisher", "").casefold() for story in cluster}
    official = any(
        re.search(r"(?:galatasaray|fenerbahce|bjk|trabzonspor|tff|uefa|fifa)", publisher)
        for publisher in publishers
    )
    newest = max((story.published for story in cluster), default=None)
    signals = TrendSignals(
        source_count=len(publishers),
        official_source=official,
        transfer=_contains(text, TRANSFER_WORDS),
        breaking=_contains(text, BREAKING_WORDS),
        injury=_contains(text, INJURY_WORDS),
        controversy=_contains(text, CONTROVERSY_WORDS),
        derby_or_big_match=_contains(text, BIG_MATCH_WORDS),
        major_team_or_player=_contains(text, MAJOR_ENTITIES),
        social_velocity=social_velocity,
        published_at=newest,
    )
    return ViralDecision(score=score_trend(signals), signals=signals)
