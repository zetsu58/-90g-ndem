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
