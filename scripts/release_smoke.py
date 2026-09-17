from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from viral_futbol.lite_video import build_lite_narration
from viral_futbol.shot_renderer import render_shot, stitch_shots
from viral_futbol.youtube_publisher import _validate_short


def require_binary(name: str) -> None:
    if not shutil.which(name):
        raise RuntimeError(f"missing runtime binary: {name}")


def main() -> int:
    for binary in ("ffmpeg", "ffprobe"):
        require_binary(binary)

    narration = build_lite_narration(
        "Galatasaray için test transfer gelişmesi",
        ["Kaynak A", "Kaynak B"],
        "tr",
        "direct",
        ["Galatasaray için test transfer gelişmesi", "İkinci bağımsız test başlığı"],
    )
    if "İkinci bağımsız test başlığı" not in narration:
        raise RuntimeError("verified fact narration gate failed")

    with tempfile.TemporaryDirectory(prefix="vf-release-") as tmp:
        root = Path(tmp)
        image = root / "frame.png"
        Image.new("RGB", (1080, 1920), "#102030").save(image)

        durations = [1.4, 1.6]
        shots = []
        for index, duration in enumerate(durations):
            path = root / f"shot-{index}.mp4"
            render_shot(image, path, duration, "micro-zoom" if index else "slow-push")
            shots.append(path)

        motion = root / "motion.mp4"
        stitch_shots(shots, motion, ["hard-cut", "push"], durations)
        if not motion.exists() or motion.stat().st_size < 10_000:
            raise RuntimeError("motion compositor gate failed")

        final = root / "release-smoke.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(motion),
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
            "-t", "12.5", "-vf", "scale=1080:1920,fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "96k", "-shortest", str(final),
        ], check=True, timeout=180)

        os.environ["SHORTS_MIN_DURATION_SECONDS"] = "1"
        quality = _validate_short(final)
        if quality["width"] != 1080 or quality["height"] != 1920:
            raise RuntimeError(f"Full HD gate failed: {quality}")

    print("[ViralFutbol] release smoke gate PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
