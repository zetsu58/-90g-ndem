from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .trend_sources import TrendItem


OFFICIAL_DOMAINS = {
    "uefa.com", "fifa.com", "tff.org", "galatasaray.org", "fenerbahce.org",
    "bjk.com.tr", "trabzonspor.org.tr",
}


@dataclass(frozen=True)
class VerificationResult:
    verified: bool
    independent_sources: int
    official_source: bool


def _domain(url: str) -> str:
    host = urlparse(url).netloc.casefold().removeprefix("www.")
    return host


def verify_items(items: list[TrendItem], *, min_sources: int = 2) -> VerificationResult:
    domains = {_domain(item.url) or item.source.casefold() for item in items}
    official = any(item.official or _domain(item.url) in OFFICIAL_DOMAINS for item in items)
    # An official announcement is strong evidence, but normal social/news claims
    # still require independent corroboration.
    verified = official or len(domains) >= min_sources
    return VerificationResult(verified, len(domains), official)
