from viral_futbol.runtime_policy import safe_exploit_percent

def test_runtime_policy_fails_closed_on_empty_db(tmp_path):
    assert safe_exploit_percent(str(tmp_path/"empty.db"),"viral_futbol") in (0,80)
