from __future__ import annotations
import json, os, subprocess, tempfile
from pathlib import Path

def enabled()->bool:return os.getenv("REMOTION_ENABLED","false").lower() in {"1","true","yes","on"}
def render(*,output:Path,title:str,caption:str,duration:float,kind:str,media:list[Path],audio:Path|None=None,music:Path|None=None)->bool:
    if not enabled(): return False
    manifest={"title":title,"caption":caption,"duration":duration,"kind":kind,"media":[p.resolve().as_uri() for p in media if p.exists()]}
    if audio and audio.exists(): manifest["audio"]=audio.resolve().as_uri()
    if music and music.exists(): manifest["music"]=music.resolve().as_uri()
    fd,name=tempfile.mkstemp(suffix=".json");os.close(fd);Path(name).write_text(json.dumps(manifest,ensure_ascii=False),encoding="utf-8")
    try:
        subprocess.run(["node","remotion/render.mjs",name,str(output)],check=True,timeout=max(180,int(os.getenv("REMOTION_TIMEOUT_SECONDS","360"))))
        return output.exists() and output.stat().st_size>1024 and b"ftyp" in output.read_bytes()[:64]
    except Exception as exc:
        print(f"Remotion render failed; FFmpeg fallback active: {exc}",flush=True);output.unlink(missing_ok=True);return False
    finally: Path(name).unlink(missing_ok=True)
