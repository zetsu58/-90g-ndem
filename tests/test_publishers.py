from viral_futbol.publishers.base import PublishResult
from viral_futbol.publishers.x_news import XNewsPublisher, build_x_news_post


def test_x_copy_contains_source_and_is_compact():
    post = build_x_news_post("Galatasaray " * 80, "https://example.com/news")
    assert "Kaynak:" in post.text
    assert len(post.text) <= 275


def test_x_publisher_is_safe_by_default():
    result = XNewsPublisher().publish(build_x_news_post("Test", "https://example.com"))
    assert result.ok is True
    assert result.external_id == "dry-run"


def test_x_live_mode_requires_transport():
    result = XNewsPublisher(dry_run=False).publish(build_x_news_post("Test", "https://example.com"))
    assert result.ok is False


def test_x_transport_can_be_injected():
    def transport(post):
        return PublishResult(ok=True, provider="x", external_id="123")

    result = XNewsPublisher(transport=transport, dry_run=False).publish(build_x_news_post("Test", "https://example.com"))
    assert result.external_id == "123"
