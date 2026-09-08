from datetime import datetime, timezone
from types import SimpleNamespace

from viral_futbol.service import Story
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


def test_turkish_payload_uses_shorts_v2_prompt():
    cluster = [Story(
        "Galatasaray transfer görüşmelerine başladı",
        "https://example.com/a",
        "Kaynak A",
        datetime.now(timezone.utc),
    )]
    payload = build_v2_payload(cluster, settings(), "tr", 82)
    prompt = payload["video_script_prompt"]
    assert "ilk 2 saniyede" in prompt
    assert "hook, event, detail, outcome, cta" in prompt
    assert "Bilgi uydurma" in prompt
    assert payload["video_aspect"] == "9:16"
    assert payload["bgm_volume"] == 0.2
