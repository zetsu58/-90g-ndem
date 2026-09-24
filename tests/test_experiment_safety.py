from viral_futbol.experiment_safety import experiment_decision

def test_rolls_back_when_exploit_materially_underperforms():
    d=experiment_decision([{"mode":"exploit","videos":12,"avg_score":70},{"mode":"explore","videos":12,"avg_score":100}])
    assert d.enabled is False and d.exploit_percent==0

def test_does_not_judge_small_samples():
    assert experiment_decision([{"mode":"exploit","videos":2,"avg_score":1},{"mode":"explore","videos":2,"avg_score":100}]).enabled
