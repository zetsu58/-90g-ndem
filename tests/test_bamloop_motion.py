from bamloop.story import motion_filter

def test_motion_presets_are_distinct():
    values={motion_filter(x,9) for x in ("push-in","pull-out","pan","parallax")}
    assert len(values)==4

def test_unknown_motion_falls_back_safely():
    assert motion_filter("unknown",9)==motion_filter("parallax",9)
