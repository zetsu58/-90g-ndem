"""Render a planned 3–4 minute video through the shared Remotion bridge."""
from __future__ import annotations
from pathlib import Path
from production.longform import plan
from production.longform_metadata import longform_metadata
from production.remotion_bridge import render
from viral_futbol.youtube_publisher import _validate_video

def render_longform(*, subject:str, channel:str, output:Path, media:list[Path], audio:Path,
                    music:Path|None=None, facts:list[str]|None=None, kind:str|None=None,
                    target_seconds:int=210, force:bool=False)->dict:
    if not media: raise ValueError("long-form requires media")
    if not audio or not audio.exists(): raise ValueError("long-form requires narration audio")
    editorial=plan(subject,channel=channel,facts=facts,target_seconds=target_seconds)
    resolved_kind=kind or ("football_story" if channel=="viral_futbol" else "explainer")
    metadata=longform_metadata(subject,channel,resolved_kind)
    output.parent.mkdir(parents=True,exist_ok=True)
    caption=editorial["scenes"][0]["narration"]
    ok=render(output=output,title=metadata["title"],caption=caption,duration=target_seconds,
              kind="football" if channel=="viral_futbol" else "explainer",media=media,audio=audio,
              music=music,content_format="video",force=force)
    if not ok: raise RuntimeError("long-form render failed")
    quality=_validate_video(output,"video")
    return {"video":str(output),"metadata":metadata,"editorial":editorial,"quality":quality}
