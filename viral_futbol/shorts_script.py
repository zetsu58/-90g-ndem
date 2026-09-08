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
    """Build the LLM instruction used by the OpenRouter layer.

    Facts are passed explicitly to discourage invented transfer fees, quotes,
    injuries or confirmations. The caller remains responsible for verification.
    """
    facts_text = "\n".join(f"- {fact}" for fact in facts if fact.strip())
    return f"""Sen Viral Futbol için Türkçe YouTube Shorts editörüsün.
Sadece aşağıdaki doğrulanmış bilgilerden yararlan. Bilgi uydurma, olmayan alıntı,
bonservis bedeli, sakatlık veya 'resmen açıklandı' ifadesi ekleme.

Başlık: {title}
Takım/konu: {team or 'belirtilmedi'}
Doğrulanmış bilgiler:
{facts_text or '- Ek doğrulanmış bilgi yok.'}

Yaklaşık {target_seconds} saniyelik metin üret ve yalnızca şu JSON alanlarını döndür:
hook, event, detail, outcome, cta

Kurallar:
- hook: ilk 2 saniyede merak uyandır, clickbait uğruna gerçeği bozma.
- event: 2-10 saniye, haberi net söyle.
- detail: 10-30 saniye, en önemli doğrulanmış ayrıntılar.
- outcome: 30-38 saniye, bunun neden önemli olduğunu açıkla.
- cta: kısa ve doğal bir yorum sorusu.
- Gereksiz giriş, selamlama ve hashtag kullanma.
""".strip()
