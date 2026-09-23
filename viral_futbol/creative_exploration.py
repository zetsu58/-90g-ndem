"""Deterministic exploit/explore policy for measured creative advice."""
from __future__ import annotations
import hashlib

def choose_creative(story_id: str, learned: dict | None, *, exploit_percent: int = 80) -> dict:
    if not learned:
        return {"mode":"baseline","apply":False}
    exploit=max(0,min(100,int(exploit_percent)))
    bucket=int(hashlib.sha256(story_id.encode()).hexdigest()[:8],16)%100
    if bucket < exploit:
        return {"mode":"exploit","apply":True,"motion":learned.get("motion"),
                "transition":learned.get("transition"),"bucket":bucket}
    return {"mode":"explore","apply":False,"bucket":bucket}
