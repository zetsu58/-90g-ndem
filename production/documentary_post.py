"""Professional documentary post-production: loudness mastering and rendered-output QC."""
from __future__ import annotations
import json,math,os,re,shutil,subprocess,tempfile
from pathlib import Path

def _measure_loudnorm(path:Path,target_lufs:float,true_peak:float,lra:float)->dict:
    completed=subprocess.run([
        "ffmpeg","-hide_banner","-nostats","-i",str(path),
        "-af",f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}:print_format=json",
        "-f","null","-"
    ],capture_output=True,text=True,timeout=max(120,int(os.getenv("LONGFORM_MASTER_MEASURE_TIMEOUT_SECONDS","300"))))
    blocks=re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}",completed.stderr or "",re.DOTALL)
    if not blocks:
        return {}
    try:
        data=json.loads(blocks[-1])
        values={
            "input_i":float(data["input_i"]),
            "input_lra":float(data["input_lra"]),
            "input_tp":float(data["input_tp"]),
            "input_thresh":float(data["input_thresh"]),
            "target_offset":float(data["target_offset"]),
        }
        return values if all(math.isfinite(x) for x in values.values()) else {}
    except (KeyError,TypeError,ValueError,json.JSONDecodeError):
        return {}

def master_audio(path:Path,target_lufs:float|None=None,true_peak:float|None=None,lra:float|None=None)->dict:
    target_lufs=float(os.getenv("LONGFORM_TARGET_LUFS","-16")) if target_lufs is None else float(target_lufs)
    true_peak=float(os.getenv("LONGFORM_TRUE_PEAK_DBTP","-1.5")) if true_peak is None else float(true_peak)
    lra=float(os.getenv("LONGFORM_TARGET_LRA","9")) if lra is None else float(lra)
    if not path.exists():
        raise ValueError("mastering_input_missing")
    measured=_measure_loudnorm(path,target_lufs,true_peak,lra)
    mode="two_pass" if measured else "single_pass_fallback"
    if measured:
        af=(
            f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra}"
            f":measured_I={measured['input_i']}:measured_LRA={measured['input_lra']}"
            f":measured_TP={measured['input_tp']}:measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}:linear=true,aresample=48000"
        )
    else:
        af=f"loudnorm=I={target_lufs}:TP={true_peak}:LRA={lra},aresample=48000"
    with tempfile.TemporaryDirectory(prefix="doc-master-") as td:
        target=Path(td)/"mastered.mp4"
        subprocess.run([
            "ffmpeg","-y","-loglevel","error","-i",str(path),
            "-map","0:v:0","-map","0:a:0","-c:v","copy","-af",af,
            "-c:a","aac","-b:a","192k","-ar","48000","-movflags","+faststart",str(target)
        ],check=True,timeout=max(180,int(os.getenv("LONGFORM_MASTER_TIMEOUT_SECONDS","600"))))
        if not target.exists() or target.stat().st_size<100000:
            raise RuntimeError("documentary_mastering_failed")
        shutil.copy2(target,path)
    return {"target_lufs":target_lufs,"true_peak":true_peak,"lra":lra,"mode":mode,"measured":measured}

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
    try:
        change_ratio=max(0.15,min(0.60,float(os.getenv("LONGFORM_QC_MIN_CHANGE_RATIO","0.32"))))
    except ValueError:
        change_ratio=0.32
    min_changes=max(10,min(28,round(expected_beats*change_ratio)))
    if visual["samples"]<expected_samples:
        raise ValueError(f"documentary_qc_samples:{visual['samples']}/{expected_samples}")
    if visual["detected_visual_changes"]<min_changes:
        raise ValueError(f"documentary_qc_visual_changes:{visual['detected_visual_changes']}/{min_changes}")
    try:
        dark_ratio=max(0.02,min(0.20,float(os.getenv("LONGFORM_QC_MAX_DARK_RATIO","0.08"))))
    except ValueError:
        dark_ratio=0.08
    if visual["dark_samples"]>max(2,round(visual["samples"]*dark_ratio)):
        raise ValueError("documentary_qc_dark_frames")
    if loudness:
        if not -19.5<=loudness["integrated_lufs"]<=-13.0:
            raise ValueError(f"documentary_qc_loudness:{loudness['integrated_lufs']}")
        if loudness["true_peak_dbtp"]>-0.5:
            raise ValueError(f"documentary_qc_true_peak:{loudness['true_peak_dbtp']}")
    return {"visual":visual,"audio":loudness,"passed":True}
