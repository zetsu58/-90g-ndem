from viral_futbol.retention_engine import build_retention_plan, retention_instruction


def test_retention_font_scales_with_viral_score():
    assert build_retention_plan(70).font_size == 74
    assert build_retention_plan(82).font_size == 78
    assert build_retention_plan(95).font_size == 82


def test_retention_instruction_keeps_fast_shorts_structure():
    plan = build_retention_plan(82)
    text = retention_instruction(plan)
    assert "İlk 2 saniyede" in text
    assert "4 kelimelik" in text
    assert "yorum sorusu" in text
    assert plan.subtitle_position == "center"
    assert plan.stroke_width == 3.0
