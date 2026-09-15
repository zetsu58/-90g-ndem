from __future__ import annotations

from dataclasses import dataclass
import re

from .service import publisher_family
from .source_intelligence import assess_sources
from .trend_score import TrendScore, TrendSignals, score_trend


@dataclass(frozen=True)
class ViralDecision:
    score: TrendScore
    signals: TrendSignals


TRANSFER_WORDS = ("transfer", "bonservis", "kiralık", "imza", "görüşme")
BREAKING_WORDS = ("son dakika", "açıkladı", "resmi", "resmen", "kap")
INJURY_WORDS = ("sakat", "sakatlık", "ameliyat", "tedavi", "mr")
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
    """Turn an already corroborated news cluster into a production decision."""
    text = " ".join(story.title for story in cluster)
    publisher_names = {
        getattr(story, "publisher", "").strip().casefold()
        for story in cluster
        if getattr(story, "publisher", "").strip()
    }
    quality = assess_sources(cluster, publisher_family)
    official_by_name = any(
        re.search(r"(?:galatasaray|fenerbahce|fenerbahçe|bjk|besiktas|beşiktaş|trabzonspor|tff|uefa|fifa)", publisher)
        for publisher in publisher_names
    )
    newest = max((story.published for story in cluster), default=None)
    signals = TrendSignals(
        source_count=quality.independent_sources,
        official_source=bool(quality.official_sources) or official_by_name,
        transfer=_contains(text, TRANSFER_WORDS),
        breaking=_contains(text, BREAKING_WORDS),
        injury=_contains(text, INJURY_WORDS),
        controversy=_contains(text, CONTROVERSY_WORDS),
        derby_or_big_match=_contains(text, BIG_MATCH_WORDS),
        major_team_or_player=_contains(text, MAJOR_ENTITIES),
        social_velocity=max(0.0, social_velocity),
        published_at=newest,
    )
    return ViralDecision(score=score_trend(signals), signals=signals)
