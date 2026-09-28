"""Lightweight, deterministic growth heuristics for Shorts.

This module is deliberately advisory: scores rank candidates and improve packaging,
but never predict virality or gate publishing. It has no network/model dependency.
"""
from __future__ import annotations
import hashlib, os, re
from dataclasses import dataclass

_WORD=re.compile(r"[a-zçğıöşü0-9]+",re.I)

def enabled(channel: str) -> bool:
    key="VIRAL_GROWTH_ENGINE_ENABLED" if channel=="viral_futbol" else "BAMLOOP_GROWTH_ENGINE_ENABLED"
    return os.getenv(key,os.getenv("GROWTH_ENGINE_ENABLED","false")).casefold() in {"1","true","yes","on"}

def _tokens(text: str) -> set[str]:
    return {x.casefold().replace("ı","i") for x in _WORD.findall(text) if len(x)>2}

def similarity(a: str,b: str) -> float:
    x,y=_tokens(a),_tokens(b)
    return len(x&y)/max(1,len(x|y))

@dataclass(frozen=True)
class GrowthDecision:
    hook: str
    hook_score: float
    topic_score: float
    fingerprint: str
    profile: str
    def as_dict(self)->dict:
        return {"hook":self.hook,"hook_score":round(self.hook_score,3),
                "topic_score":round(self.topic_score,3),"fingerprint":self.fingerprint,
                "profile":self.profile}

def hook_score(text: str) -> float:
    """Explainable heuristic, not a success probability."""
    words=_WORD.findall(text)
    if not words:return 0.0
    specificity=min(1.0,sum(ch.isdigit() for ch in text)/2+min(len(words),12)/18)
    clarity=1.0 if 4<=len(words)<=14 else 0.55
    curiosity=0.85 if any(x in text.casefold() for x in ("neden","nasıl","işte","ama","sonra","gerçek","what","why","how","but")) else 0.55
    tension=0.8 if any(x in text.casefold() for x in ("son dakika","kritik","şaş","değiş","kriz","breaking","shock","change")) else 0.5
    return (specificity+clarity+curiosity+tension)/4

def topic_score(*,age_minutes: float=30,source_count: int=1,visual_ready: bool=True,
                duplicate_similarity: float=0.0,outlier_multiple: float|None=None)->float:
    freshness=max(0.0,1-min(max(age_minutes,0),180)/180)
    corroboration=min(1.0,max(source_count,0)/3)
    visual=1.0 if visual_ready else 0.35
    duplicate=max(0.0,1-min(max(duplicate_similarity,0),1))
    outlier=0.5 if outlier_multiple is None else min(1.0,max(0.0,outlier_multiple/4))
    return .30*freshness+.20*corroboration+.15*visual+.20*duplicate+.15*outlier

def _hooks(subject: str, profile: str)->list[str]:
    clean=" ".join(subject.split()).strip(" .")
    if profile=="bamloop":
        return [f"Tam her şey bitti derken {clean}",f"{clean} ama sonunu kimse beklemiyordu",f"Bu hikâyede asıl sürpriz: {clean}"]
    return [f"Son dakika: {clean}",f"{clean} — peki bu neden önemli?",f"{clean}: şimdi ne değişecek?"]

def decide(subject: str,*,profile: str,age_minutes: float=30,source_count: int=1,
           recent_titles: list[str]|None=None,outlier_multiple: float|None=None)->GrowthDecision:
    recent_titles=recent_titles or []
    dup=max((similarity(subject,x) for x in recent_titles),default=0.0)
    candidates=_hooks(subject,profile)
    hook=max(candidates,key=hook_score)
    fp=hashlib.sha256((profile+"|"+ " ".join(sorted(_tokens(subject)))).encode()).hexdigest()[:24]
    return GrowthDecision(hook,hook_score(hook),topic_score(age_minutes=age_minutes,
        source_count=source_count,duplicate_similarity=dup,outlier_multiple=outlier_multiple),fp,profile)

def packaging_warnings(title: str,opening_text: str="")->list[str]:
    warnings=[]
    if len(title)>100:warnings.append("title_too_long")
    if len(_tokens(title))<3:warnings.append("title_too_vague")
    if opening_text and similarity(title,opening_text)>.8:warnings.append("title_opening_duplicate")
    return warnings
