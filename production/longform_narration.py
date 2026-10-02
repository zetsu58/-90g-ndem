"""Generate a grounded long-form narration with an optional OpenAI-compatible LLM."""
from __future__ import annotations
import json,os,re,urllib.request

def _words(text:str)->list[str]:
    return re.findall(r"\S+",text)

def _supported_numbers(text:str,claims:list[str])->bool:
    allowed=set(re.findall(r"\b\d+(?:[.,]\d+)?\b"," ".join(claims)))
    used=set(re.findall(r"\b\d+(?:[.,]\d+)?\b",text))
    return used.issubset(allowed)

def _llm(prompt:str,claims:list[str],low:int,high:int)->str|None:
    base=os.getenv("LONGFORM_LLM_BASE_URL","").strip().rstrip("/")
    model=os.getenv("LONGFORM_LLM_MODEL","").strip()
    if not base or not model:
        return None
    endpoint=base if base.endswith("/chat/completions") else base+"/chat/completions"
    headers={"Content-Type":"application/json"}
    key=os.getenv("LONGFORM_LLM_API_KEY","").strip()
    if key:
        headers["Authorization"]="Bearer "+key
    body=json.dumps({"model":model,"temperature":0.2,"messages":[
        {"role":"system","content":"Yalnızca verilen doğrulanmış olguları kullanan dikkatli bir Türkçe belgesel editörüsün. Bilgi uydurma."},
        {"role":"user","content":prompt}
    ]}).encode()
    try:
        req=urllib.request.Request(endpoint,data=body,headers=headers,method="POST")
        with urllib.request.urlopen(req,timeout=max(20,int(os.getenv("LONGFORM_LLM_TIMEOUT_SECONDS","90")))) as response:
            data=json.loads(response.read())
        text=str((((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    except Exception as exc:
        print(f"Longform LLM deferred: {type(exc).__name__}",flush=True)
        return None
    count=len(_words(text))
    if count < low or count > int(high*1.10) or not _supported_numbers(text,claims):
        print("Longform LLM output rejected by grounding/length gate",flush=True)
        return None
    return text

def fallback_narration(subject:str,claims:list[str],low:int,high:int)->str:
    intro=(
        f"Bu videoda {subject} konusunu doğrulanmış kayıtların izin verdiği ölçüde adım adım ele alıyoruz. "
        "Amaç, tek bir başlığa bakıp sonuç çıkarmak değil; eldeki olguları kronolojik ve anlaşılır bir akışta bir araya getirmek. "
        "Doğrulanmayan ayrıntıları eklemiyor, kaynakların söylemediği sonuçları kesin bilgi gibi sunmuyoruz."
    )
    transitions=(
        "İlk doğrulanmış nokta şu:",
        "Kronolojideki bir sonraki kayıt şöyle:",
        "Başka bir doğrulanmış bilgi de şu:",
        "Kayıtlarda yer alan bir diğer nokta şöyle:",
        "Konunun devamında doğrulanabilen bilgi şu:",
        "Bu tabloya eklenen bir başka kayıt da şu:"
    )
    parts=[intro]
    for i,claim in enumerate(claims):
        parts.append(f"{transitions[i%len(transitions)]} {claim} Bu bilgi, anlatının doğrulanmış parçalarından biri olarak ele alınmalı; bunun ötesindeki yorumları olgu gibi sunmuyoruz.")
    recap_index=0
    target=max(low,min(high-30,round((low+high)/2)))
    while len(_words(" ".join(parts))) < target-35 and claims:
        claim=claims[recap_index%len(claims)]
        parts.append(f"Toparlarken yeniden altını çizmek gereken kayıt şu: {claim} Bu noktayı diğer doğrulanmış kayıtlarla birlikte okumak, konuyu tek bir iddiaya indirgemeden anlamaya yardımcı oluyor.")
        recap_index+=1
        if recap_index>len(claims)*2:
            break
    outro=(
        f"Sonuç olarak {subject} hakkında güvenli biçimde söylenebilecek çerçeve bu doğrulanmış kayıtlarla sınırlı. "
        "Yeni ve güvenilir bilgi geldikçe tablo değişebilir; bu yüzden kesin olmayan ayrıntıları kesinmiş gibi eklemek yerine doğrulanmış veriyi esas almak en doğru yaklaşım."
    )
    parts.append(outro)
    text=" ".join(parts)
    words=_words(text)
    if len(words)>high:
        text=" ".join(words[:max(low,min(high-18,len(words)))])+" Yeni doğrulanmış bilgiler geldikçe bu dosya güncellenebilir."
    return text

def generate_narration(subject:str,script_contract:dict)->dict:
    claims=list(script_contract.get("verified_claims") or [])
    low=int(script_contract.get("min_words") or 450)
    high=int(script_contract.get("max_words") or 585)
    text=_llm(str(script_contract.get("prompt") or ""),claims,low,high)
    provider="llm" if text else "grounded_fallback"
    if not text:
        text=fallback_narration(subject,claims,low,high)
    count=len(_words(text))
    if count < low or not _supported_numbers(text,claims):
        raise ValueError("narration_grounding_gate_failed")
    return {"text":text,"word_count":count,"provider":provider}
