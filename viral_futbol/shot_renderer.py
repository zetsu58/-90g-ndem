from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def _motion_filter(motion: str) -> str:
    motions = {
        "slow-push": "scale=900:1600,crop=720:1280:x='67+19*t':y='120+9*t'",
        "parallax": "scale=920:1636,crop=720:1280:x='75+34*sin(t*0.9)':y='135+21*cos(t*0.7)'",
        "whip-pan": "scale=940:1672,crop=720:1280:x='82+64*sin(t*1.8)':y='147+13*cos(t)'",
        "micro-zoom": "scale=880:1566,crop=720:1280:x='60+13*sin(t)':y='107+13*cos(t)'",
        "punch-in": "scale=960:1707,crop=720:1280:x='90+26*sin(t*1.4)':y='158+22*cos(t)'",
        "slide": "scale=900:1600,crop=720:1280:x='67+41*sin(t*0.65)':y=120",
        "crop-pan": "scale=920:1636,crop=720:1280:x='75+39*sin(t*0.72)':y='135+15*cos(t)'",
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
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-threads", "1",
        "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(command, check=True, timeout=90)


def render_brand_intro(logo: Path, output: Path, duration: float = 0.8) -> None:
    """Render a lightweight heartbeat-style logo sting without loading Chromium."""
    seconds = max(0.6, min(1.2, duration))
    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-filter_threads", "1",
        "-f", "lavfi", "-i", f"color=c=#050505:s=720x1280:r=30:d={seconds:.2f}",
        "-loop", "1", "-framerate", "30", "-i", str(logo),
        "-filter_complex",
        "[1:v]format=rgba,scale='220+34*sin(2*PI*t/0.28)':'-1':eval=frame[mark];"
        "[0:v][mark]overlay=(W-w)/2:(H-h)/2:shortest=1,"
        "fade=t=in:st=0:d=0.08,fade=t=out:st=0.68:d=0.12,format=yuv420p[v]",
        "-map", "[v]", "-an", "-t", f"{seconds:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "1",
        "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(command, check=True, timeout=60)


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
