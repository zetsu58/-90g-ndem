from datetime import datetime, timezone

from viral_futbol.trend_score import TrendSignals, score_trend
from viral_futbol.trend_sources import TrendItem
from viral_futbol.verification import verify_items


def test_hot_official_transfer_is_produced():
    result = score_trend(TrendSignals(
        source_count=2,
        official_source=True,
        transfer=True,
        social_velocity=0.9,
        published_at=datetime.now(timezone.utc),
    ))
    assert result.score == 100
    assert result.decision == "produce"


def test_weak_single_source_is_ignored():
    result = score_trend(TrendSignals(source_count=1))
    assert result.decision == "ignore"


def test_two_independent_domains_verify():
    now = datetime.now(timezone.utc)
    items = [
        TrendItem("x", "https://example.com/a", "one", now),
        TrendItem("x", "https://example.org/b", "two", now),
    ]
    assert verify_items(items).verified is True


def test_official_domain_verifies():
    now = datetime.now(timezone.utc)
    items = [TrendItem("x", "https://www.uefa.com/a", "UEFA", now)]
    result = verify_items(items)
    assert result.verified is True
    assert result.official_source is True
