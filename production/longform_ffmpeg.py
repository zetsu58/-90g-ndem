"""Low-memory FFmpeg fallback for documentary 16:9 long-form renders."""
from __future__ import annotations
import os,subprocess,tempfile
from pathlib import Path

VIDEO_EXTENSIONS={".mp4",".mov",".webm",".m4v",".ogv"}

def _ass_time(ms:float)->str:
    total=max(0.0,float(ms))/1000.0
    h=int(total//3600);m=int((total%3600)//60);s=total%60
    return f"{h}:{m:02d}:{s:05.2f}"

def _ass_escape(text:str)->str:
    return str(text).replace("\\","\\\\").replace("{","\\{").replace("}","\\}").replace("\n","\\N")

def _write_ass(path:Path,captions:list[dict])->None:
    header="""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Doc,DejaVu Sans,25,&H00FFFFFF,&H00FFFFFF,&H00101010,&H88000000,-1,0,0,0,100,100,0,0,3,1,0,2,110,110,24,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines=[header]
    for page in captions:
        text=_ass_escape(page.get("text") or "")
        if not text:
            continue
        lines.append(f"Dialogue: 0,{_ass_time(page.get('startMs',0))},{_ass_time(page.get('endMs',0))},Doc,,0,0,0,,{text}\n")
    path.write_text("".join(lines),encoding="utf-8")

def render_slideshow(*,media:list[Path],scenes:list[dict],audio:Path,output:Path,music:Path|None=None,
                     beats:list[dict]|None=None,captions:list[dict]|None=None)->None:
    if not media or not scenes:
        raise ValueError("longform_ffmpeg_requires_media_and_scenes")
    timeline=beats or [
        {"start":float(scene.get("start") or 0),"duration":float(scene.get("duration") or 8),
         "mediaIndex":index%len(media),"motion":scene.get("motion")}
        for index,scene in enumerate(scenes)
    ]
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="longform-ffmpeg-") as td:
        root=Path(td);clips=[]
        for index,beat in enumerate(timeline):
            source=Path(media[int(beat.get("mediaIndex") or 0)%len(media)])
            duration=max(2.0,float(beat.get("duration") or 5.0))
            clip=root/f"beat-{index:03d}.mp4"
            vf=(
                "scale=1408:792:force_original_aspect_ratio=increase,"
                "crop=1280:720:x='64+14*sin(t*0.42)':y='36+8*cos(t*0.31)',"
                "fps=30,format=yuv420p,"
                f"fade=t=in:st=0:d=0.14,fade=t=out:st={max(0.14,duration-0.14):.2f}:d=0.14"
            )
            if source.suffix.lower() in VIDEO_EXTENSIONS:
                cmd=["ffmpeg","-y","-loglevel","error","-stream_loop","-1","-i",str(source),"-t",f"{duration:.3f}",
                     "-vf",vf,"-an","-c:v","libx264","-preset","veryfast","-crf","21","-threads","1",
                     "-pix_fmt","yuv420p",str(clip)]
            else:
                cmd=["ffmpeg","-y","-loglevel","error","-filter_threads","1","-loop","1","-framerate","30","-i",str(source),
                     "-t",f"{duration:.3f}","-vf",vf,"-an","-c:v","libx264","-preset","veryfast","-crf","21","-threads","1",
                     "-pix_fmt","yuv420p",str(clip)]
            subprocess.run(cmd,check=True,timeout=max(90,int(duration*6)))
            clips.append(clip)
        manifest=root/"clips.txt"
        manifest.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips),encoding="utf-8")
        video=root/"video.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(manifest),"-an","-c","copy",str(video)],
                       check=True,timeout=240)

        subtitle_filter=None
        if captions:
            ass=root/"captions.ass";_write_ass(ass,captions)
            subtitle_filter=f"ass={ass}"

        if music and Path(music).exists():
            mix="[1:a]volume=1.06,acompressor=threshold=0.14:ratio=2.5:attack=5:release=100[voice];[2:a]volume=0.10[bed];[voice][bed]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.94[a]"
            cmd=["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),"-stream_loop","-1","-i",str(music),
                 "-filter_complex",mix,"-map","0:v","-map","[a]"]
        else:
            mix="[1:a]volume=1.06,acompressor=threshold=0.14:ratio=2.5:attack=5:release=100,alimiter=limit=0.94[a]"
            cmd=["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),"-filter_complex",mix,
                 "-map","0:v","-map","[a]"]
        if subtitle_filter:
            cmd.extend(["-vf",subtitle_filter,"-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p"])
        else:
            cmd.extend(["-c:v","copy"])
        cmd.extend(["-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(output)])
        subprocess.run(cmd,check=True,timeout=max(300,int(os.getenv("LONGFORM_FFMPEG_TIMEOUT_SECONDS","1500"))))
    if not output.exists() or output.stat().st_size<100000:
        raise RuntimeError("longform_ffmpeg_output_invalid")
