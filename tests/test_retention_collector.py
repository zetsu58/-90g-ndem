from viral_futbol.retention_collector import SCOPE

def test_retention_uses_readonly_analytics_scope():
    assert SCOPE == "https://www.googleapis.com/auth/yt-analytics.readonly"
