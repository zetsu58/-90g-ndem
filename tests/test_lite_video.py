from viral_futbol.lite_video import _edge_voice, build_lite_narration


def test_edge_voice_normalizes_legacy_gender_suffix():
    assert _edge_voice("tr-TR-AhmetNeural-Male", "tr") == "tr-TR-AhmetNeural"
    assert _edge_voice("en-US-GuyNeural-Male", "en") == "en-US-GuyNeural"


def test_lite_narration_is_factual_and_branded():
    text = build_lite_narration(
        "Galatasaray için yeni transfer gelişmesi",
        ["TRT Spor", "NTV Spor"],
        "tr",
    )
    assert "Galatasaray" in text
    assert "TRT Spor" not in text
    assert "NTV Spor" not in text
    assert "90+ Gündem" in text
    assert len(text) <= 350
    assert text.startswith("Galatasaray")
    assert "resmî açıklama" not in text
    assert "takipte kalın" not in text
    assert "Gelişmeler geldikçe" not in text
