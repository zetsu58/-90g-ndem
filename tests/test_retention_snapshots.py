from viral_futbol.retention_snapshots import RetentionSnapshotStore
def test_snapshot_buckets(tmp_path):
    with RetentionSnapshotStore(str(tmp_path/"r.db")) as s:
        assert s.record("s","v",25,[{"elapsed_ratio":0.0,"audience_watch_ratio":1.0}])==24
        assert s.record("s","v",100,[{"elapsed_ratio":0.0,"audience_watch_ratio":.5}])==168
