from viral_futbol.scene_learning import recommended_scene_creative


def test_no_scene_advice_without_evidence(tmp_path):
    assert recommended_scene_creative(str(tmp_path/"empty.db")) is None
