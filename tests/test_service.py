from datetime import datetime, timezone

from integrations.viral_futbol.config import Settings
from integrations.viral_futbol.service import Story, publisher_family, title_similarity, verified_clusters


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
