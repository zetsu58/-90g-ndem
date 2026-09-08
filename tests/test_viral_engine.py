from datetime import datetime, timezone

from viral_futbol.service import Story
from viral_futbol.viral_engine import evaluate_cluster


def story(title: str, publisher: str) -> Story:
    return Story(title, "https://example.com", publisher, datetime.now(timezone.utc))


def test_major_breaking_transfer_is_produced():
    cluster = [
        story("Galatasaray transfer görüşmesini resmen açıkladı", "Galatasaray"),
        story("Galatasaray'da son dakika transfer gelişmesi", "TRT Spor"),
    ]
    decision = evaluate_cluster(cluster, social_velocity=0.9)
    assert decision.score.score >= 75
    assert decision.score.decision == "produce"


def test_low_interest_story_is_not_auto_produced():
    cluster = [
        story("Takım haftanın antrenmanını tamamladı", "Kaynak A"),
        story("Takım antrenmana çıktı", "Kaynak B"),
    ]
    decision = evaluate_cluster(cluster)
    assert decision.score.decision != "produce"
