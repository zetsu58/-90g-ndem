from viral_futbol.worker import WorkerConfig


def test_worker_config_has_safe_minimums(monkeypatch):
    monkeypatch.setenv("NEWS_WORKER_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("NEWS_WORKER_ERROR_BACKOFF_SECONDS", "1")
    config = WorkerConfig.from_env()
    assert config.interval_seconds == 30
    assert config.error_backoff_seconds == 5
