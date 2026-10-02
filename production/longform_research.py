"""Evidence contract for long-form videos. Network retrieval stays upstream."""
from __future__ import annotations
import hashlib,re
from dataclasses import dataclass,asdict

@dataclass(frozen=True)
class Evidence:
    claim:str
    source:str
    url:str=""
    official:bool=False

def build_fact_manifest(subject:str,evidence:list[Evidence],*,min_claims:int=5)->dict:
    subject=re.sub(r"\s+"," ",subject).strip()
    clean=[]
    seen=set()
    for item in evidence:
        claim=re.sub(r"\s+"," ",item.claim).strip()
        source=re.sub(r"\s+"," ",item.source).strip()
        if not claim or not source: continue
        key=claim.casefold()
        if key in seen: continue
        seen.add(key); clean.append(Evidence(claim,source,item.url.strip(),item.official))
    independent={x.source.casefold() for x in clean}
    if len(clean)<min_claims: raise ValueError("insufficient_evidence")
    if len(independent)<2 and not any(x.official for x in clean): raise ValueError("insufficient_corroboration")
    return {"id":hashlib.sha256((subject+"|"+"|".join(x.claim for x in clean)).encode()).hexdigest()[:24],
            "subject":subject,"claims":[asdict(x) for x in clean],"claim_count":len(clean),
            "independent_sources":len(independent),"official_sources":sum(x.official for x in clean),
            "ready":True}
