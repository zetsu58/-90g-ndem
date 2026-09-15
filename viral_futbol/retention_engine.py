from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPlan:
    subtitle_position: str = "center"
    font_size: int = 76
    stroke_width: float = 3.0
    words_per_caption: int = 4
    hook_seconds: int = 2
    cta_seconds: int = 3


def build_retention_plan(viral_score: int) -> RetentionPlan:
    """Short, readable caption blocks tuned for vertical football Shorts."""
    size = 82 if viral_score >= 90 else 78 if viral_score >= 80 else 74
    return RetentionPlan(font_size=size)


def retention_instruction(plan: RetentionPlan) -> str:
    return (
        f"İlk {plan.hook_seconds} saniyede tek cümlelik güçlü bir kanca kullan. "
        "Cümleleri kısa ve seslendirmeye uygun tut. Ekran altyazısında aynı anda "
        f"yaklaşık {plan.words_per_caption} kelimelik kısa bloklar hedefle. "
        "Oyuncu, takım, skor ve 'son dakika' gibi anlam taşıyan kelimeleri cümlede "
        "erken kullan. Son bölümde kısa bir yorum sorusu bırak."
    )
