from __future__ import annotations

import subprocess
from pathlib import Path


def _motion_filter(motion: str) -> str:
    motions = {
        "slow-push": "scale=900:1600,crop=720:1280:x='90+25*t':y='160+12*t'",
        "parallax": "scale=920:1640,crop=720:1280:x='100+45*sin(t*0.9)':y='180+28*cos(t*0.7)'",
        "whip-pan": "scale=940:1670,crop=720:1280:x='110+85*sin(t*1.8)':y='195+18*cos(t)'",
        "micro-zoom": "scale=880:1565,crop=720:1280:x='80+18*sin(t)':y='142+18*cos(t)'",
        "punch-in": "scale=960:1707,crop=720:1280:x='120+35*sin(t*1.4)':y='210+30*cos(t)'",
        "slide": "scale=900:1600,crop=720:1280:x='90+55*sin(t*0.65)':y=160",
        "crop-pan": "scale=920:1640,crop=720:1280:x='100+52*sin(t*0.72)':y='180+20*cos(t)'",
    }
    return motions.get(motion, motions["slow-push"]) + ",fps=30,format=yuv420p"


def render_shot(image: Path, output: Path, duration: float, motion: str) -> None:
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", "30", "-i", str(image),
        "-t", f"{max(0.8, duration):.2f}",
        "-vf", _motion_filter(motion),
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(command, check=True, timeout=90)


def stitch_shots(shots: list[Path], output: Path) -> None:
    if not shots:
        raise ValueError("No rendered shots")
    concat = output.with_suffix(".shots.txt")
    concat.write_text("\n".join(f"file '{shot.resolve()}'" for shot in shots) + "\n", encoding="utf-8")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(concat), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-an", str(output),
        ], check=True, timeout=180)
    finally:
        concat.unlink(missing_ok=True)
