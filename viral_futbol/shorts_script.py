from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShortsScript:
    hook: str
    event: str
    detail: str
    outcome: str
    cta: str

    @property
    def narration(self) -> str:
        return " ".join((self.hook, self.event, self.detail, self.outcome, self.cta)).strip()


def build_script_prompt(*, title: str, facts: list[str], team: str = "", target_seconds: int = 18) -> str:
    """Build a narration-first prompt for MoneyPrinterTurbo/OpenRouter.

    The model must return plain spoken Turkish because the generated response is
    consumed as narration. Structured timing is expressed as editorial guidance,
    not as JSON fields that could accidentally be read by TTS.
    """
    facts_text = "\n".join(f"- {fact}" for fact in facts if fact.strip())
    target_seconds = max(12, min(60, int(target_seconds)))
    event_end = round(target_seconds * .45)
    detail_end = max(event_end + 1, target_seconds - 3)
    return f"""Sen Viral Futbol için Türkçe YouTube Shorts editörüsün.
Sadece aşağıdaki haber bilgilerinden yararlan. Tek kaynaklı iddiayı kesinleşmiş gibi sunma. Bilgi uydurma; olmayan alıntı,
bonservis bedeli, sakatlık, sağlık sonucu veya kesinleşmemiş bir gelişme için
'resmen açıklandı' ifadesi ekleme.

Başlık: {title}
Takım/konu: {team or 'belirtilmedi'}
Haber bilgileri:
{facts_text or '- Ek bilgi yok.'}

Yaklaşık {target_seconds} saniyelik TEK PARÇA doğal Türkçe seslendirme metni üret.
Yalnızca seslendirilecek metni döndür. JSON, başlık, madde işareti, zaman kodu,
sahne etiketi, açıklama veya hashtag döndürme.

Akış:
- İlk 2 saniye: takım/oyuncu ve en önemli doğru bilgiyi doğrudan söyle.
- 2-{event_end} saniye: gelişmeyi açık ve hızlı anlat.
- {event_end}-{detail_end} saniye: tek önemli desteklenen ayrıntıyı ver.
- {detail_end}-{target_seconds} saniye: kısa sonuç veya özgün değerlendirme.
- Uzun kapanış, takip çağrısı ve sırf süre dolduran yorum sorusu ekleme.

Kısa cümleler kullan. Kaynak URL'lerini seslendirme. Gereksiz giriş ve selamlama yapma.
""".strip()
