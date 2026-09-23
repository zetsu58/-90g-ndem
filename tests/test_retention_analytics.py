from viral_futbol.retention_analytics import fetch_retention

class Q:
    def query(self, **kwargs):
        assert kwargs["dimensions"]=="elapsedVideoTimeRatio"
        assert "audienceWatchRatio" in kwargs["metrics"]
        return self
    def execute(self):
        return {"columnHeaders":[{"name":"elapsedVideoTimeRatio"},{"name":"audienceWatchRatio"},{"name":"relativeRetentionPerformance"},{"name":"stoppedWatching"}],
                "rows":[[0.01,1.0,0.6,2],[0.02,0.9,0.55,3]]}
class API:
    def reports(self): return Q()

def test_fetch_retention_curve():
    points=fetch_retention(API(),video_id="abc",start_date="2026-09-01",end_date="2026-09-23")
    assert len(points)==2
    assert points[1]["audience_watch_ratio"]==0.9
