from viral_futbol.scene_manifest import SceneManifestStore
from viral_futbol.scene_performance import ScenePerformanceStore, record_story_scene_snapshot


def test_scene_snapshot_and_learning_threshold(tmp_path):
    db=str(tmp_path/"vf.db")
    with SceneManifestStore(db) as manifests:
        manifests.plan("s1","Derbi haberi",10)
    result=record_story_scene_snapshot(db,"s1",age_hours=20,views=1000,likes=50,comments=10,performance_score=72)
    assert result["snapshot_hours"] == 24
    assert result["scenes_recorded"] >= 3
    with ScenePerformanceStore(db) as store:
        assert store.leaders() == []  # no creative rule from a single sample
