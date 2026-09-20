from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def _motion_filter(motion: str) -> str:
    motions = {
        "slow-push": "scale=675:1200,crop=540:960:x='67+19*t':y='120+9*t'",
        "parallax": "scale=690:1227,crop=540:960:x='75+34*sin(t*0.9)':y='135+21*cos(t*0.7)'",
        "whip-pan": "scale=705:1254,crop=540:960:x='82+64*sin(t*1.8)':y='147+13*cos(t)'",
        "micro-zoom": "scale=660:1174,crop=540:960:x='60+13*sin(t)':y='107+13*cos(t)'",
        "punch-in": "scale=720:1280,crop=540:960:x='90+26*sin(t*1.4)':y='158+22*cos(t)'",
        "slide": "scale=675:1200,crop=540:960:x='67+41*sin(t*0.65)':y=120",
        "crop-pan": "scale=690:1227,crop=540:960:x='75+39*sin(t*0.72)':y='135+15*cos(t)'",
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
        "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "21", "-threads", "1",
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
