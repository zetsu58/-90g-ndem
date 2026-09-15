from datetime import datetime, timezone
from types import SimpleNamespace

from viral_futbol.service import Story, build_payload
from viral_futbol.service_v2 import build_v2_payload


def settings():
    return SimpleNamespace(
        voice_name="tr-TR-AhmetNeural",
        english_voice_name="en-US-GuyNeural",
        voice_rate=1.0,
        video_source="pexels",
        video_clip_duration=3,
        bgm_type="random",
        bgm_volume=0.2,
    )


def sample_cluster():
    return [Story(
        "Galatasaray transfer görüşmelerine başladı",
        "https://example.com/a",
        "Kaynak A",
        datetime.now(timezone.utc),
    )]


def test_turkish_payload_uses_narration_only_shorts_v2_prompt():
    payload = build_v2_payload(sample_cluster(), settings(), "tr", 82)
    prompt = payload["video_script_prompt"]

    assert "İlk 2 saniye" in prompt
    assert "TEK PARÇA" in prompt
    assert "JSON, başlık" in prompt
    assert "Bilgi uydurma" in prompt
    assert "hook, event, detail, outcome, cta" not in prompt
    assert "JSON dışına çıkma" not in payload["custom_system_prompt"]
    assert "tek parça seslendirme metni" in payload["custom_system_prompt"]
    assert payload["video_aspect"] == "9:16"
    assert payload["video_clip_duration"] == 3
    assert payload["subtitle_enabled"] is True
    assert payload["subtitle_position"] == "center"
    assert payload["font_size"] == 78
    assert payload["stroke_width"] == 3.0
    assert payload["bgm_volume"] == 0.2


def test_v2_does_not_add_unknown_mpt_payload_keys():
    cluster = sample_cluster()
    legacy = build_payload(cluster, settings(), "tr")
    v2 = build_v2_payload(cluster, settings(), "tr", 82)

    assert set(v2) == set(legacy)
    assert "video_terms" not in v2
    assert v2["video_subject"].startswith(cluster[0].title)
