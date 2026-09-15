from viral_futbol.media_engine import build_media_plan, material_terms


def test_transfer_plan_uses_team_and_transfer_context():
    plan = build_media_plan(
        "Galatasaray yeni transfer için görüşmelere başladı",
        ["Galatasaray transfer görüşmelerini sürdürüyor"],
    )
    assert plan.context == "transfer"
    assert "Galatasaray" in plan.entities
    terms = material_terms(plan)
    assert any("Galatasaray" in term for term in terms)
    assert any("transfer" in term for term in terms)


def test_generic_story_has_safe_football_broll():
    plan = build_media_plan("Takım hazırlıklarını tamamladı", [])
    assert plan.context == "news"
    assert all("football" in term for term in material_terms(plan))
