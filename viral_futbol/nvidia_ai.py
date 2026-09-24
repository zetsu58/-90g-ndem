from __future__ import annotations

import json
import os
import urllib.request


def generate_narration(*, title: str, facts: list[str], language: str, fallback: str) -> str:
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if not key or os.getenv("NVIDIA_AI_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return fallback

    endpoint = os.getenv("NVIDIA_API_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
    model = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
    records = "\n".join("- " + item.strip() for item in facts if item.strip())
    system = (
        "Sen Viral Futbol için dikkatli bir Türkçe Shorts editörüsün. Yalnızca verilen "
        "haber olgularını kullan; bilgi, alıntı, ücret, sağlık sonucu veya resmi durum uydurma. "
        "Yalnızca doğal seslendirme metni döndür."
        if language == "tr"
        else "You are a careful football Shorts editor. Use only supplied facts. Return narration only."
    )
    prompt = (
        f"Başlık: {title}\nKayıtlar:\n{records}\n30-40 saniyelik, 75-100 kelimelik Türkçe "
        "Shorts metni yaz. İlk 2 saniyede doğru bir kanca kullan, önemini açıkla ve tek soruyla bitir."
        if language == "tr"
        else f"Title: {title}\nRecords:\n{records}\nWrite a 75-100 word football Shorts narration."
    )
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}], "temperature": 0.35, "max_tokens": 220, "stream": False}).encode()
    req = urllib.request.Request(endpoint + "/chat/completions", data=body, headers={"Authorization": "Bearer " + key, "Accept": "application/json", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=max(5, int(os.getenv("NVIDIA_TIMEOUT_SECONDS", "35")))) as response:
            result = json.loads(response.read())
        generated = str(result["choices"][0]["message"]["content"]).strip()
        return generated or fallback
    except Exception as exc:
        print(f"ViralFutbol NVIDIA fallback: {type(exc).__name__}", flush=True)
        return fallback
