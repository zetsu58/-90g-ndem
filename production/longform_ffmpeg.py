"""Low-memory FFmpeg fallback for 16:9 long-form renders."""
from __future__ import annotations
import os,subprocess,tempfile
from pathlib import Path

def render_slideshow(*,media:list[Path],scenes:list[dict],audio:Path,output:Path,music:Path|None=None)->None:
    if not media or not scenes:
        raise ValueError("longform_ffmpeg_requires_media_and_scenes")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="longform-ffmpeg-") as td:
        root=Path(td);clips=[]
        for index,scene in enumerate(scenes):
            source=media[index%len(media)]
            duration=max(2.0,float(scene.get("duration") or 8.0))
            clip=root/f"scene-{index:03d}.mp4"
            vf=(
                "scale=1408:792:force_original_aspect_ratio=increase,"
                "crop=1280:720:x='64+18*sin(t*0.35)':y='36+10*cos(t*0.27)',"
                "fps=30,format=yuv420p,"
                f"fade=t=in:st=0:d=0.20,fade=t=out:st={max(0.2,duration-0.20):.2f}:d=0.20"
            )
            subprocess.run(["ffmpeg","-y","-loglevel","error","-filter_threads","1","-loop","1","-framerate","30","-i",str(source),
                            "-t",f"{duration:.2f}","-vf",vf,"-an","-c:v","libx264","-preset","veryfast","-crf","21","-threads","1",
                            "-pix_fmt","yuv420p",str(clip)],check=True,timeout=max(90,int(duration*5)))
            clips.append(clip)
        manifest=root/"clips.txt"
        manifest.write_text("".join(f"file '{clip.resolve()}'\n" for clip in clips),encoding="utf-8")
        video=root/"video.mp4"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0","-i",str(manifest),"-an","-c","copy",str(video)],
                       check=True,timeout=180)
        if music and Path(music).exists():
            mix="[1:a]volume=1.05,acompressor=threshold=0.14:ratio=2.5:attack=5:release=100[voice];[2:a]volume=0.12[bed];[voice][bed]amix=inputs=2:duration=first:dropout_transition=2:normalize=0,alimiter=limit=0.94[a]"
            cmd=["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),"-stream_loop","-1","-i",str(music),
                 "-filter_complex",mix,"-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(output)]
        else:
            cmd=["ffmpeg","-y","-loglevel","error","-i",str(video),"-i",str(audio),"-map","0:v","-map","1:a",
                 "-c:v","copy","-c:a","aac","-b:a","192k","-shortest","-movflags","+faststart",str(output)]
        subprocess.run(cmd,check=True,timeout=max(300,int(os.getenv("LONGFORM_FFMPEG_TIMEOUT_SECONDS","1200"))))
    if not output.exists() or output.stat().st_size<100000:
        raise RuntimeError("longform_ffmpeg_output_invalid")
