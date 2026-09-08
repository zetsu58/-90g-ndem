from viral_futbol.visual_quality import build_visual_quality_plan, prioritized_terms


def test_known_entity_is_prioritized_for_hook():
    plan = build_visual_quality_plan(("Galatasaray", "Osimhen"), "transfer")
    terms = prioritized_terms(["Galatasaray football stadium", "football fans"], plan)
    assert terms[0] == "Galatasaray football close up"
    assert terms[1] == "Osimhen football close up"
    assert plan.clip_duration == 3


def test_terms_are_deduplicated():
    plan = build_visual_quality_plan((), "news")
    terms = prioritized_terms(["football stadium", "football stadium", "football fans"], plan)
    assert len(terms) == len(set(term.casefold() for term in terms))
