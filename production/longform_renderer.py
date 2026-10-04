"""Render a verified 3–4 minute documentary through Remotion with FFmpeg fallback."""
from __future__ import annotations
import os
from pathlib import Path
from production.longform import plan
from production.longform_metadata import longform_metadata
from production.longform_script import build_script
from production.remotion_bridge import render
from production.longform_ffmpeg import render_slideshow
from production.documentary_post import master_audio, inspect_documentary
from viral_futbol.youtube_publisher import _validate_video

def low_memory_ffmpeg_enabled()->bool:
    return os.getenv("LONGFORM_FORCE_FFMPEG","false").casefold() in {"1","true","yes","on"}

def _lower_third(scene:dict)->str:
    text=str(scene.get("narration") or "").strip()
    if ":" in text:
        text=text.split(":",1)[1].strip()
    words=text.split()
    return " ".join(words[:18]) + ("…" if len(words)>18 else "")

def render_longform(*, subject:str, channel:str, output:Path, media:list[Path], audio:Path,
                    music:Path|None=None, facts:list[str]|None=None, fact_manifest:dict|None=None,
                    kind:str|None=None, target_seconds:int=210, force:bool=False,
                    visual_beats:list[dict]|None=None,captions:list[dict]|None=None)->dict:
    if not media:
        raise ValueError("long-form requires media")
    if not audio or not audio.exists():
        raise ValueError("long-form requires narration audio")
    if fact_manifest is None or not fact_manifest.get("ready"):
        raise ValueError("verified fact manifest required")
    script_contract=build_script(subject,fact_manifest,target_seconds)
    verified_facts=script_contract["verified_claims"]
    editorial=plan(subject,channel=channel,facts=verified_facts,target_seconds=target_seconds)
    resolved_kind=kind or ("football_story" if channel=="viral_futbol" else "explainer")
    metadata=longform_metadata(subject,channel,resolved_kind)
    output.parent.mkdir(parents=True,exist_ok=True)
    remotion_scenes=[
        {"start":scene["start"],"duration":scene["duration"],"caption":_lower_third(scene),
         "mediaIndex":index%len(media),"motion":scene["motion"],"section":scene["section"]}
        for index,scene in enumerate(editorial["scenes"])
    ]
    caption=_lower_third(editorial["scenes"][0])
    diagnostic={}
    force_ffmpeg=low_memory_ffmpeg_enabled()
    if force_ffmpeg:
        ok=False
        diagnostic["bypassed"]="low_memory_ffmpeg"
    else:
        ok=render(output=output,title=metadata["title"],caption=caption,duration=target_seconds,
                  kind="football" if channel=="viral_futbol" else "explainer",media=media,audio=audio,
                  music=music,content_format="video",scenes=remotion_scenes,beats=visual_beats or [],captions=captions or [],
                  force=force,diagnostic=diagnostic)
    renderer="remotion"
    if not ok:
        render_slideshow(media=media,scenes=editorial["scenes"],audio=audio,output=output,music=music,
                         beats=visual_beats or [],captions=captions or [])
        renderer="ffmpeg"
    mastering=master_audio(output)
    quality=_validate_video(output,"video")
    post_qc=inspect_documentary(output,len(visual_beats or []),float(target_seconds))
    return {"video":str(output),"metadata":metadata,"editorial":editorial,
            "script_contract":script_contract,"quality":quality,"renderer":renderer,
            "visual_beat_count":len(visual_beats or []),"caption_pages":len(captions or []),
            "mastering":mastering,"post_qc":post_qc,"render_diagnostic":diagnostic}

def render_contract(contract:dict,output:Path,force:bool=False)->dict:
    if not contract.get("ready_for_render"):
        raise ValueError("producer contract is not render ready")
    return render_longform(subject=contract["subject"],channel=contract["channel"],output=output,
                           media=contract["media"],audio=contract["audio"],music=contract.get("music"),
                           fact_manifest=contract["manifest"],kind=contract["metadata"].get("kind"),
                           target_seconds=int(contract["metadata"].get("target_seconds") or 210),force=force,
                           visual_beats=contract.get("visual_beats"),captions=contract.get("captions"))
