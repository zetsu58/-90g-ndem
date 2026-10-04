"""Professional documentary post-production: loudness mastering and rendered-output QC."""
from __future__ import annotations
import json,math,os,re,subprocess,tempfile
from pathlib import Path

def master_audio(path:Path,target_lufs:float=-16.0,true_peak:float=-1.5,lra:float=9.0)->dict:
    if not path.exists():
        raise ValueError("mastering_input_missing")
    with tempfile.TemporaryDirectory(prefix="doc-master-") as td:
        target=Path(td)/"mastered.mp4"
        af=f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra},aresample=48000"
        subprocess.run([
            "ffmpeg","-y","-loglevel","error","-i",str(path),
            "-map","0:v:0","-map","0:a:0","-c:v","copy","-af",af,
            "-c:a","aac","-b:a","192k","-ar","48000","-movflags","+faststart",str(target)
        ],check=True,timeout=max(180,int(os.getenv("LONGFORM_MASTER_TIMEOUT_SECONDS","600"))))
        if not target.exists() or target.stat().st_size<100000:
            raise RuntimeError("documentary_mastering_failed")
        target.replace(path)
    return {"target_lufs":target_lufs,"true_peak":true_peak,"lra":lra}

def _loudness(path:Path)->dict:
    completed=subprocess.run([
        "ffmpeg","-hide_banner","-nostats","-i",str(path),
        "-af","loudnorm=I=-16:TP=-1.5:LRA=9:print_format=json","-f","null","-"
    ],capture_output=True,text=True,timeout=180)
    stderr=completed.stderr or ""
    blocks=re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}",stderr,re.DOTALL)
    if not blocks:
        return {}
    try:
        data=json.loads(blocks[-1])
        return {
            "integrated_lufs":float(data.get("input_i")),
            "true_peak_dbtp":float(data.get("input_tp")),
            "lra":float(data.get("input_lra")),
        }
    except (TypeError,ValueError,json.JSONDecodeError):
        return {}

def _visual_samples(path:Path,interval:float=5.0)->dict:
    width,height=32,18;frame_bytes=width*height
    completed=subprocess.run([
        "ffmpeg","-v","error","-i",str(path),
        "-vf",f"crop=iw:ih*0.70:0:0,fps=1/{max(1.0,interval)},scale={width}:{height},format=gray",
        "-f","rawvideo","-pix_fmt","gray","pipe:1"
    ],capture_output=True,timeout=180,check=True)
    raw=completed.stdout or b""
    frames=[raw[i:i+frame_bytes] for i in range(0,len(raw)-frame_bytes+1,frame_bytes)]
    transitions=0;dark=0;diffs=[]
    for frame in frames:
        if sum(frame)/max(1,len(frame))<10:
            dark+=1
    for left,right in zip(frames,frames[1:]):
        diff=sum(abs(a-b) for a,b in zip(left,right))/frame_bytes
        diffs.append(diff)
        if diff>=7.0:
            transitions+=1
    return {
        "samples":len(frames),
        "detected_visual_changes":transitions,
        "dark_samples":dark,
        "mean_frame_delta":round(sum(diffs)/max(1,len(diffs)),2),
    }

def inspect_documentary(path:Path,expected_beats:int,target_seconds:float=210.0)->dict:
    interval=max(4.0,min(6.0,target_seconds/max(1,expected_beats)))
    visual=_visual_samples(path,interval)
    loudness=_loudness(path)
    expected_samples=max(8,math.floor(target_seconds/interval)-2)
    min_changes=max(10,min(24,round(expected_beats*0.32)))
    if visual["samples"]<expected_samples:
        raise ValueError(f"documentary_qc_samples:{visual['samples']}/{expected_samples}")
    if visual["detected_visual_changes"]<min_changes:
        raise ValueError(f"documentary_qc_visual_changes:{visual['detected_visual_changes']}/{min_changes}")
    if visual["dark_samples"]>max(2,round(visual["samples"]*0.08)):
        raise ValueError("documentary_qc_dark_frames")
    if loudness:
        if not -19.5<=loudness["integrated_lufs"]<=-13.0:
            raise ValueError(f"documentary_qc_loudness:{loudness['integrated_lufs']}")
        if loudness["true_peak_dbtp"]>-0.5:
            raise ValueError(f"documentary_qc_true_peak:{loudness['true_peak_dbtp']}")
    return {"visual":visual,"audio":loudness,"passed":True}
