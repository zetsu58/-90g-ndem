from viral_futbol.scene_manifest import SceneManifestStore


def test_scene_manifest_is_durable_and_repairable(tmp_path):
    db = str(tmp_path / "vf.db")
    with SceneManifestStore(db) as store:
        scenes = store.plan("story-1", "Galatasaray transfer gelişmesi", 10)
        assert len(scenes) >= 3
        assert scenes[0]["state"] == "planned"
        store.mark_asset("story-1", 0, asset_path="/tmp/scene0.jpg", state="ready")
        assert store.scenes("story-1")[0]["revision"] == 2
        assert all(row["scene_index"] != 0 for row in store.repairable("story-1"))

    with SceneManifestStore(db) as store:
        assert store.scenes("story-1")[0]["asset_path"] == "/tmp/scene0.jpg"
