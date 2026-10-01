"""Shared content-format profiles for Shorts and regular YouTube videos."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ContentProfile:
    name: str
    min_seconds: float
    max_seconds: float
    width: int
    height: int
    orientation: str
    target_seconds: int

PROFILES = {
    "short": ContentProfile("short", 12, 70, 720, 1280, "vertical", 40),
    "video": ContentProfile("video", 150, 300, 1280, 720, "landscape", 210),
}

def profile(name: str | None) -> ContentProfile:
    key=(name or "short").casefold().strip()
    if key not in PROFILES:
        raise ValueError(f"Unknown content profile: {key}")
    return PROFILES[key]

def football_longform_brief(subject: str, kind: str="player_career") -> dict:
    """Deterministic editorial contract; factual research stays upstream."""
    if kind not in {"player_career","club_history","football_story"}:
        raise ValueError("Unsupported football long-form kind")
    return {
        "format":"video","kind":kind,"subject":subject,"target_seconds":210,
        "sections":[
            {"name":"hook","seconds":12},
            {"name":"origins","seconds":38},
            {"name":"rise","seconds":50},
            {"name":"turning_points","seconds":55},
            {"name":"legacy_now","seconds":40},
            {"name":"outro","seconds":15},
        ],
        "rules":["Doğrulanmış olgular kullan","Tarih ve kulüp isimlerini kaynaklarla çapraz kontrol et",
                 "Görseli anlatılan dönemle eşleştir","Aynı görüntüyü uzun süre sabit tutma"],
    }

def explainer_longform_brief(subject: str) -> dict:
    return {
        "format":"video","kind":"explainer","subject":subject,"target_seconds":210,
        "sections":[
            {"name":"hook","seconds":12},{"name":"what","seconds":45},
            {"name":"how","seconds":55},{"name":"examples","seconds":55},
            {"name":"takeaway","seconds":28},{"name":"outro","seconds":15},
        ],
        "rules":["Tek ana soru etrafında kal","Kısa cümleler kullan","Her bölümde yeni görsel kanıt veya örnek göster",
                 "Doğrulanamayan ayrıntıyı kesin bilgi gibi sunma"],
    }
