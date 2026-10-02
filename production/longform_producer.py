"""Safe orchestration contract for a future long-form producer."""
from __future__ import annotations
import hashlib
from pathlib import Path
from production.longform_research import Evidence,build_fact_manifest
from production.longform_script import build_script
from production.longform import plan
from production.longform_metadata import longform_metadata

def prepare_contract(*,subject:str,channel:str,evidence:list[Evidence],kind:str|None=None,target_seconds:int=210,min_claims:int=5)->dict:
    manifest=build_fact_manifest(subject,evidence,min_claims=min_claims)
    script=build_script(subject,manifest,target_seconds)
    editorial=plan(subject,channel=channel,facts=script["verified_claims"],target_seconds=target_seconds)
    resolved=kind or ("football_story" if channel=="viral_futbol" else "explainer")
    metadata=longform_metadata(subject,channel,resolved)
    digest=hashlib.sha256((channel+"|"+subject+"|"+manifest["id"]).encode()).hexdigest()
    metadata.update({"content_format":"video","evidence_id":manifest["id"],"target_seconds":target_seconds})
    return {"content_id":digest[:24],"content_hash":digest,"subject":subject,"channel":channel,
            "manifest":manifest,"script":script,"editorial":editorial,"metadata":metadata,
            "ready_for_assets":True,"ready_for_render":False}

def attach_assets(contract:dict,*,media:list[Path],audio:Path,music:Path|None=None)->dict:
    if not contract.get("ready_for_assets"): raise ValueError("contract_not_ready")
    existing=[Path(x) for x in media if Path(x).exists()]
    if len(existing)<3: raise ValueError("insufficient_media")
    audio=Path(audio)
    if not audio.exists() or audio.stat().st_size<1: raise ValueError("narration_missing")
    value=dict(contract)
    value.update({"media":existing,"audio":audio,"music":Path(music) if music else None,
                  "ready_for_render":True})
    return value
