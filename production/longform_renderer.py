"""Render a verified 3–4 minute video through Remotion with FFmpeg fallback."""
from __future__ import annotations
from pathlib import Path
from production.longform import plan
from production.longform_metadata import longform_metadata
from production.longform_script import build_script
from production.remotion_bridge import render
from production.longform_ffmpeg import render_slideshow
from viral_futbol.youtube_publisher import _validate_video

def render_longform(*, subject:str, channel:str, output:Path, media:list[Path], audio:Path,
                    music:Path|None=None, facts:list[str]|None=None, fact_manifest:dict|None=None,
                    kind:str|None=None, target_seconds:int=210, force:bool=False)->dict:
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
        {"start":scene["start"],"duration":scene["duration"],"caption":scene["narration"],
         "mediaIndex":index%len(media),"motion":scene["motion"]}
        for index,scene in enumerate(editorial["scenes"])
    ]
    caption=editorial["scenes"][0]["narration"]
    diagnostic={}
    ok=render(output=output,title=metadata["title"],caption=caption,duration=target_seconds,
              kind="football" if channel=="viral_futbol" else "explainer",media=media,audio=audio,
              music=music,content_format="video",scenes=remotion_scenes,force=force,diagnostic=diagnostic)
    renderer="remotion"
    if not ok:
        render_slideshow(media=media,scenes=editorial["scenes"],audio=audio,output=output,music=music)
        renderer="ffmpeg"
    quality=_validate_video(output,"video")
    return {"video":str(output),"metadata":metadata,"editorial":editorial,
            "script_contract":script_contract,"quality":quality,"renderer":renderer,
            "render_diagnostic":diagnostic}

def render_contract(contract:dict,output:Path,force:bool=False)->dict:
    if not contract.get("ready_for_render"):
        raise ValueError("producer contract is not render ready")
    return render_longform(subject=contract["subject"],channel=contract["channel"],output=output,
                           media=contract["media"],audio=contract["audio"],music=contract.get("music"),
                           fact_manifest=contract["manifest"],kind=contract["metadata"].get("kind"),
                           target_seconds=int(contract["metadata"].get("target_seconds") or 210),force=force)
