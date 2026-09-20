from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def _motion_filter(motion: str) -> str:
    motions = {
        "slow-push": "scale=1350:2400,crop=1080:1920:x='135+38*t':y='240+18*t'",
        "parallax": "scale=1380:2453,crop=1080:1920:x='150+68*sin(t*0.9)':y='270+42*cos(t*0.7)'",
        "whip-pan": "scale=1410:2507,crop=1080:1920:x='165+128*sin(t*1.8)':y='293+27*cos(t)'",
        "micro-zoom": "scale=1320:2347,crop=1080:1920:x='120+27*sin(t)':y='213+27*cos(t)'",
        "punch-in": "scale=1440:2560,crop=1080:1920:x='180+53*sin(t*1.4)':y='315+45*cos(t)'",
        "slide": "scale=1350:2400,crop=1080:1920:x='135+83*sin(t*0.65)':y=240",
        "crop-pan": "scale=1380:2453,crop=1080:1920:x='150+78*sin(t*0.72)':y='270+30*cos(t)'",
    }
    return motions.get(motion, motions["slow-push"]) + ",fps=30,format=yuv420p"


def render_shot(image: Path, output: Path, duration: float, motion: str) -> None:
    seconds = max(0.8, duration)
    visual_filter = _motion_filter(motion) + f",fade=t=in:st=0:d=0.12,fade=t=out:st={seconds-0.12:.2f}:d=0.12"
    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-filter_threads", "1",
        "-loop", "1", "-framerate", "30", "-i", str(image),
        "-t", f"{seconds:.2f}",
        "-vf", visual_filter,
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "1",
        "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(command, check=True, timeout=90)


def stitch_shots(
    shots: list[Path],
    output: Path,
    transitions: list[str] | None = None,
    durations: list[float] | None = None,
) -> None:
    if not shots:
        raise ValueError("No rendered shots")
    if len(shots) == 1:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(shots[0]), "-c", "copy", str(output)],
            check=True,
            timeout=90,
        )
        return

    # xfade keeps every 1080p input open simultaneously and OOMs on Render's
    # 512 MB instance. Each shot already carries a short fade transition.
    with tempfile.TemporaryDirectory(prefix="shorts-concat-") as directory:
        manifest = Path(directory) / "clips.txt"
        manifest.write_text("".join(f"file '{shot.resolve()}'\n" for shot in shots))
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(manifest), "-an", "-c", "copy", str(output),
        ], check=True, timeout=90)
