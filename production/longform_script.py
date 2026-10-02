"""Deterministic long-form script contract built only from verified evidence."""
from __future__ import annotations
import re
from production.longform import narration_budget

def build_script(subject:str,manifest:dict,target_seconds:int=210)->dict:
    if not manifest.get("ready"): raise ValueError("fact_manifest_not_ready")
    claims=[re.sub(r"\s+"," ",str(x.get("claim",""))).strip() for x in manifest.get("claims",[]) if str(x.get("claim","")).strip()]
    if len(claims)<5: raise ValueError("insufficient_verified_claims")
    low,high=narration_budget(target_seconds)
    prompt=f"""Türkçe, doğal ve belgesel temposunda yaklaşık {target_seconds} saniyelik anlatım yaz.
Konu: {subject}
Yalnızca aşağıdaki doğrulanmış olguları kullan:
"""+"\n".join(f"- {x}" for x in claims)+f"""
Hedef uzunluk: {low}-{high} kelime.
Güçlü ama gerçeği bozmayan bir giriş yap. Kronolojiyi veya mantıksal akışı koru.
Doğrulanmamış sayı, tarih, transfer bedeli, alıntı veya başarı ekleme.
Kaynak URL'si, hashtag, JSON veya sahne etiketi yazma."""
    return {"subject":subject,"target_seconds":target_seconds,"min_words":low,"max_words":high,
            "prompt":prompt.strip(),"evidence_id":manifest.get("id"),"verified_claims":claims}
