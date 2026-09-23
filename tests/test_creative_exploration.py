from viral_futbol.creative_exploration import choose_creative

def test_exploration_is_deterministic():
    advice={"motion":"push-in","transition":"whip"}
    assert choose_creative("same",advice)==choose_creative("same",advice)

def test_no_evidence_keeps_baseline():
    assert choose_creative("x",None)["mode"]=="baseline"
