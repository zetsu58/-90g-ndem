from viral_futbol import x_pipeline


def test_x_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("X_PUBLISH_ENABLED", raising=False)
    assert x_pipeline.x_publish_enabled() is False


def test_x_enable_switch(monkeypatch):
    monkeypatch.setenv("X_PUBLISH_ENABLED", "true")
    assert x_pipeline.x_publish_enabled() is True


def test_non_turkish_cluster_is_not_published(monkeypatch):
    monkeypatch.setenv("X_PUBLISH_ENABLED", "true")
    assert x_pipeline.publish_verified_cluster([object()], language="en") is None
