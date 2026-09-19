from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

OFFICIAL_HOST_MARKERS = (
    "tff.org", "uefa.com", "fifa.com",
    "galatasaray.org", "fenerbahce.org", "bjk.com.tr", "trabzonspor.org.tr",
)
LOW_SIGNAL_HOST_MARKERS = ("facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com")


@dataclass(frozen=True)
class SourceQuality:
    independent_sources: int
    official_sources: int
    low_signal_sources: int
    score: int
    reasons: tuple[str, ...]


def _host(story) -> str:
    raw = str(getattr(story, "link", "") or getattr(story, "url", "") or "")
    return (urlparse(raw).hostname or "").lower().removeprefix("www.")


def assess_sources(cluster, family_resolver) -> SourceQuality:
    """Score corroboration quality without making network requests.

    The caller supplies its canonical publisher-family resolver so syndicated
    copies from one media group count as a single source.
    """
    families = {
        family_resolver(str(getattr(story, "publisher", "") or ""))
        for story in cluster
        if str(getattr(story, "publisher", "") or "").strip()
    }
    hosts = {_host(story) for story in cluster if _host(story)}
    official = sum(any(marker in host for marker in OFFICIAL_HOST_MARKERS) for host in hosts)
    low_signal = sum(any(marker in host for marker in LOW_SIGNAL_HOST_MARKERS) for host in hosts)

    score = min(60, len(families) * 20) + min(25, official * 25) - min(30, low_signal * 10)
    reasons = [f"{len(families)} bağımsız yayıncı"]
    if official:
        reasons.append(f"{official} resmi kaynak")
    if low_signal:
        reasons.append(f"{low_signal} düşük sinyalli sosyal kaynak")
    return SourceQuality(
        independent_sources=len(families),
        official_sources=official,
        low_signal_sources=low_signal,
        score=max(0, min(100, score)),
        reasons=tuple(reasons),
    )


REPUTABLE_PUBLISHERS = (
    'bbc', 'reuters', 'associated press', 'ap news', 'anadolu ajansı', 'aa',
    'ntv', 'trt spor', 'bein sports', 'sky sports', 'the athletic', 'espn',
    'guardian', 'marca', 'as', 'l equipe', 'lequipe', 'uefa', 'fifa', 'tff',
    'galatasaray', 'fenerbahçe', 'beşiktaş', 'trabzonspor',
)
CONFLICT_PAIRS = (
    ('yalanladı','doğruladı'), ('reddetti','kabul etti'),
    ('ayrıldı','kaldı'), ('iptal','onay'), ('sakat','sağlıklı'),
)


def confidence_gate(cluster, family_resolver):
    """Reputable breaking stories pass alone; social claims require corroboration."""
    quality = assess_sources(cluster, family_resolver)
    titles = [str(s.title).casefold() for s in cluster]
    for yes, no in CONFLICT_PAIRS:
        if any(yes in title for title in titles) and any(no in title for title in titles):
            return False, 'conflict', quality
    publishers = [str(s.publisher).casefold() for s in cluster]
    reputable = any(any(name in publisher for name in REPUTABLE_PUBLISHERS) for publisher in publishers)
    if quality.official_sources or (reputable and quality.low_signal_sources == 0):
        return True, 'reputable', quality
    if quality.independent_sources >= 2 and quality.low_signal_sources == 0:
        return True, 'corroborated', quality
    return False, 'source', quality
