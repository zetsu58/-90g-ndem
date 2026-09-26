from unittest.mock import patch

from scripts.run_worker import cycle


def test_disabled_x_never_fetches_newsroom(monkeypatch):
    monkeypatch.setenv("X_PUBLISH_ENABLED", "false")
    with patch("scripts.run_worker.trend_gate", return_value={"top": []}), \
         patch("scripts.run_worker.fetch_x_newsroom", side_effect=AssertionError("X network called")), \
         patch("scripts.run_worker.run_once_v2", return_value={"fetched": 0}), \
         patch("scripts.run_worker.publish_ready", return_value={"published": 0}), \
         patch("scripts.run_worker.collect_youtube_performance", return_value={}):
        result = cycle()
    assert result["x"]["disabled"] is True
    assert result["shorts"] == {"fetched": 0}
