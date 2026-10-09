"""Review-only micro-sketchs inspired by short product/brand comedy beats.

The reference Shorts identify topics, not footage to reuse. This module can
make an animatic from original keyframes; it does not enqueue or upload it.
Actual publication requires a separately reviewed moving-picture master.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

REFERENCES = (
    {"id": "old_phone_surprise", "reference": "https://youtube.com/shorts/plgsvMUaa18",
     "premise": "A battered old keypad phone surprises a modern phone by working after a fall.",
     "beat": "setup → impact → old phone works → modern phone reacts"},
    {"id": "old_phone_last_word", "reference": "https://youtube.com/shorts/9APUgRN-BYU",
     "premise": "A modern phone boasts about progress; the old phone has the last word.",
     "beat": "boast → unexpected interruption → quick reaction"},
    {"id": "soda_car", "reference": "https://youtube.com/shorts/KDJ7jTj1DxM",
     "premise": "A soda brand imagines building a car, then meets an unexpected rival concept.",
     "beat": "bold idea → reveal → surprising rival"},
)


def render_animatic(first: Path, punchline: Path, output: Path) -> dict:
    """Render a six-second *preview* with original keyframes and visible motion.

    This output is deliberately marked as review-only in the manifest. Still
    frames with a camera move are not a finished animated sketch.
    """
    from PIL import Image

    for path in (first, punchline):
        if not path.is_file():
            raise FileNotFoundError(path)
        with Image.open(path) as image:
            if image.width / image.height < .5 or image.width / image.height > .62:
                raise ValueError("A vertical 9:16 keyframe is required")
    if hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(punchline.read_bytes()).digest():
        raise ValueError("Setup and punchline keyframes must differ")
    output.parent.mkdir(parents=True, exist_ok=True)
    # A small moving camera and a hard beat cut keep the staging legible.
    filters = (
        "[0:v]scale=760:1352,crop=720:1280:x='20+8*sin(t*1.5)':y='36+8*t',"
        "fps=30,trim=duration=2.8,setpts=PTS-STARTPTS[a];"
        "[1:v]scale=760:1352,crop=720:1280:x='20-8*sin(t*1.4)':y='36-5*t',"
        "fps=30,trim=duration=3.2,setpts=PTS-STARTPTS[b];"
        "[a][b]concat=n=2:v=1:a=0,format=yuv420p[v]"
    )
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-loop", "1", "-framerate", "30", "-i", str(first),
               "-loop", "1", "-framerate", "30", "-i", str(punchline),
               "-filter_complex", filters, "-map", "[v]", "-t", "6",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-movflags", "+faststart", str(output)]
    subprocess.run(command, check=True)
    manifest = {"status": "review_only", "content_type": "brand_sketch_animatic",
                "published": False, "reference_ids": [item["id"] for item in REFERENCES],
                "video": str(output), "keyframes": [str(first), str(punchline)],
                "quality_note": "Keyframe animatic; moving character animation and sound are still required."}
    output.with_suffix(".json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render a review-only BAMLOOP micro-sketch animatic")
    parser.add_argument("first", type=Path)
    parser.add_argument("punchline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(render_animatic(args.first, args.punchline, args.output), ensure_ascii=False))
