from __future__ import annotations
import os,time
from dataclasses import dataclass

@dataclass(frozen=True)
class WorkDecision:
    shorts:bool
    longform:bool
    reason:str

def decide(now=None,last_longform_at=None,longform_enabled=None,interval_hours=None):
    from production.publishing_policy import shorts_only
    if shorts_only():
        return WorkDecision(True,False,"shorts_only_policy")
    now=time.time() if now is None else now
    enabled=(os.getenv("LONGFORM_ENABLED","false").lower() in ("1","true","yes","on")) if longform_enabled is None else longform_enabled
    if not enabled:
        return WorkDecision(True,False,"longform_disabled")
    raw_interval=os.getenv("LONGFORM_INTERVAL_HOURS","24") if interval_hours is None else interval_hours
    interval=max(6,float(raw_interval))*3600
    due=last_longform_at is None or now-last_longform_at>=interval
    return WorkDecision(True,due,"longform_due" if due else "longform_not_due")

def channel_kind(channel,sequence=0):
    if channel=="viral_futbol":
        return ("player_career","club_history","football_story")[sequence%3]
    if channel=="bamloop":
        return "explainer"
    raise ValueError("unsupported channel")
