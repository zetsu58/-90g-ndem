from datetime import datetime, timezone

from viral_futbol.config import Settings
from viral_futbol.service import (
    Store,
    Story,
    build_payload,
    news_editions,
    publisher_family,
    title_similarity,
    verified_clusters,
)


def _cluster() -> list[Story]:
    now = datetime.now(timezone.utc)
    return [
        Story("Club begins talks with player", "https://a.test/1", "Source A", now),
        Story("Club starts talks with player", "https://b.test/2", "Source B", now),
    ]


def test_similar_headlines_match():
    assert title_similarity(
        "Galatasaray yeni transfer için görüşmelere başladı",
        "Galatasaray transfer görüşmelerine başladı",
    ) > 0.52


def test_cluster_requires_distinct_publishers():
    now = datetime.now(timezone.utc)
    stories = [
        Story("Fenerbahçe yıldız oyuncuyla görüşmelere başladı", "https://a.test/1", "A Spor", now),
        Story("Fenerbahçe yıldız oyuncu için görüşmelere başladı", "https://b.test/2", "NTV Spor", now),
    ]
    result = verified_clusters(stories, Settings(min_sources=2, similarity=0.52))
    assert len(result) == 1


def test_same_publisher_is_not_verification():
    now = datetime.now(timezone.utc)
    stories = [
        Story("Beşiktaş yeni transferi açıkladı", "https://a.test/1", "A", now),
        Story("Beşiktaş yeni transferini açıkladı", "https://a.test/2", "A", now),
    ]
    assert verified_clusters(stories, Settings(min_sources=2, similarity=0.52)) == []


def test_sibling_brand_labels_are_one_source():
    assert publisher_family("NTV Haber") == publisher_family("NTVSpor")


def test_default_editions_include_turkish_and_global_english():
    editions = news_editions(Settings())
    assert [(language, country) for language, country, _ in editions] == [
        ("tr", "TR"),
        ("en", "US"),
    ]


def test_english_payload_uses_global_voice_and_fast_quality_profile():
    payload = build_payload(_cluster(), Settings(), "en")
    assert payload["video_language"] == "en"
    assert payload["voice_name"] == "en-US-GuyNeural-Male"
    assert payload["video_clip_duration"] == 5
    assert payload["video_aspect"] == "9:16"
    assert "global English" in payload["video_script_prompt"]


def test_dedupe_key_is_language_specific():
    cluster = _cluster()
    assert Store.story_id(cluster, "tr") != Store.story_id(cluster, "en")
