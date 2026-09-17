from __future__ import annotations

import subprocess
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
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", "30", "-i", str(image),
        "-t", f"{max(0.8, duration):.2f}",
        "-vf", _motion_filter(motion),
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(command, check=True, timeout=90)


def stitch_shots(shots: list[Path], output: Path, transitions: list[str] | None = None) -> None:
    if not shots:
        raise ValueError("No rendered shots")
    if len(shots) == 1:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(shots[0]), "-c", "copy", str(output)], check=True, timeout=90)
        return

    transitions = transitions or ["hard-cut"] * len(shots)
    inputs: list[str] = []
    for shot in shots:
        inputs.extend(["-i", str(shot)])

    # Short xfade transitions keep the pace high while avoiding slideshow-like cuts.
    duration = 0.16
    offset = 2.04
    filters = []
    previous = "[0:v]"
    for index in range(1, len(shots)):
        kind = transitions[index % len(transitions)]
        effect = {"whip": "slideleft", "push": "smoothleft", "flash": "fadeblack"}.get(kind, "fade")
        out = f"[v{index}]"
        filters.append(
            f"{previous}[{index}:v]xfade=transition={effect}:duration={duration:.2f}:offset={offset:.2f}{out}"
        )
        previous = out
        offset += max(0.8, 2.6 - duration)

    command = [
        "ffmpeg", "-y", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(filters),
        "-map", previous, "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-pix_fmt", "yuv420p", str(output),
    ]
    subprocess.run(command, check=True, timeout=240)
