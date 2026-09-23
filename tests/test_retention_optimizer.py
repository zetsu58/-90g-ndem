from viral_futbol.retention_optimizer import recommended_retention_creative

def test_optimizer_refuses_thin_evidence(tmp_path):
    assert recommended_retention_creative(str(tmp_path/"empty.db")) is None
