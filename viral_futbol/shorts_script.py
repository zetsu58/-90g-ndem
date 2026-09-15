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


def build_script_prompt(*, title: str, facts: list[str], team: str = "", target_seconds: int = 40) -> str:
    """Build a narration-first prompt for MoneyPrinterTurbo/OpenRouter.

    The model must return plain spoken Turkish because the generated response is
    consumed as narration. Structured timing is expressed as editorial guidance,
    not as JSON fields that could accidentally be read by TTS.
    """
    facts_text = "\n".join(f"- {fact}" for fact in facts if fact.strip())
    return f"""Sen Viral Futbol için Türkçe YouTube Shorts editörüsün.
Sadece aşağıdaki doğrulanmış bilgilerden yararlan. Bilgi uydurma; olmayan alıntı,
bonservis bedeli, sakatlık, sağlık sonucu veya kesinleşmemiş bir gelişme için
'resmen açıklandı' ifadesi ekleme.

Başlık: {title}
Takım/konu: {team or 'belirtilmedi'}
Doğrulanmış bilgiler:
{facts_text or '- Ek doğrulanmış bilgi yok.'}

Yaklaşık {target_seconds} saniyelik TEK PARÇA doğal Türkçe seslendirme metni üret.
Yalnızca seslendirilecek metni döndür. JSON, başlık, madde işareti, zaman kodu,
sahne etiketi, açıklama veya hashtag döndürme.

Akış:
- İlk 2 saniye: gerçeği bozmayan güçlü bir merak kancası.
- 2-10 saniye: gelişmeyi açık ve hızlı anlat.
- 10-30 saniye: en önemli doğrulanmış ayrıntıları ver.
- 30-38 saniye: gelişmenin neden önemli olduğunu söyle.
- Son 2-3 saniye: kısa ve doğal bir yorum sorusu sor.

Kısa cümleler kullan. Kaynak URL'lerini seslendirme. Gereksiz giriş ve selamlama yapma.
""".strip()
