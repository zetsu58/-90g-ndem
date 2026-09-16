from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemeIdea:
    query: str
    caption: str
    title: str


IDEAS = (
    MemeIdea("funny car fail", "PLAN BAŞKA\nSONUÇ BAŞKA 💀", "Plan Başkaydı, Sonuç Çok Başka Oldu 💀"),
    MemeIdea("robot technology fail", "TEKNOLOJİYE\nFAZLA GÜVENDİ 🤖", "Teknolojiye Biraz Fazla Güvendi 🤖"),
    MemeIdea("funny dog surprise", "SONUNU O DA\nBEKLEMİYORDU 😂", "Sonunu O da Beklemiyordu 😂"),
    MemeIdea("skateboard funny fail", "1 SANİYE SONRA... 💀", "Bir Saniye Sonra Her Şey Değişti 💀"),
    MemeIdea("funny gym fail", "ÖZGÜVEN: %100\nSONUÇ: 💀", "Özgüven Yüksek, Sonuç Fena 💀"),
    MemeIdea("unexpected water splash", "TAM BİTTİ DERKEN... 😂", "Tam Bitti Derken Olanlar Oldu 😂"),
)


def choose_idea(seed: str | None = None) -> MemeIdea:
    chooser = random.Random(seed)
    return chooser.choice(IDEAS)


def _request_json(url: str, api_key: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Authorization": api_key, "User-Agent": "BAMLOOP/1.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def find_licensed_clip(query: str, api_key: str) -> tuple[str, str]:
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY is required for licensed source clips")
    params = urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "size": "medium", "per_page": 20}
    )
    payload = _request_json(f"https://api.pexels.com/videos/search?{params}", api_key)
    candidates: list[tuple[int, str, str]] = []
    for video in payload.get("videos", []):
        creator = str((video.get("user") or {}).get("name") or "Pexels Creator")
        page_url = str(video.get("url") or "https://www.pexels.com")
        for file in video.get("video_files", []):
            width = int(file.get("width") or 0)
            height = int(file.get("height") or 0)
            link = str(file.get("link") or "")
            if link and height >= width and height >= 720:
                candidates.append((height, link, f"{creator} — {page_url}"))
    if not candidates:
        raise RuntimeError(f"No portrait Pexels video found for: {query}")
    candidates.sort(reverse=True)
    _, url, attribution = candidates[min(2, len(candidates) - 1)]
    return url, attribution


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "BAMLOOP/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    if destination.stat().st_size < 10_000:
        raise RuntimeError("Downloaded clip is unexpectedly small")


def _escape_drawtext_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def build_video(
    idea: MemeIdea,
    output_dir: str = "storage/bamloop",
    source_url: str | None = None,
) -> tuple[Path, dict]:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{idea.query}|{idea.caption}|{source_url or ''}".encode()).hexdigest()[:16]
    output = directory / f"bamloop-{key}.mp4"
    if output.exists() and output.stat().st_size > 10_000:
        return output, {"title": idea.title, "caption": idea.caption, "cached": True}

    attribution = "Provided source clip"
    if source_url is None:
        source_url, attribution = find_licensed_clip(idea.query, os.getenv("PEXELS_API_KEY", "").strip())
    source = directory / f"{key}-source.mp4"
    caption_file = directory / f"{key}-caption.txt"
    _download(source_url, source)
    caption_file.write_text(idea.caption, encoding="utf-8")

    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    caption_path = _escape_drawtext_path(caption_file)
    video_filter = (
        "[0:v]trim=start=0:end=3,setpts=PTS-STARTPTS,"
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,eq=contrast=1.08:saturation=1.18:brightness=0.02,"
        "fps=30,split=2[forward][backward];"
        "[backward]reverse[reverse];"
        "[forward][reverse]concat=n=2:v=1:a=0,"
        "drawtext=fontfile="
        f"{font}:textfile='{caption_path}':reload=0:"
        "fontcolor=white:fontsize=64:borderw=5:bordercolor=black:"
        "box=1:boxcolor=black@0.62:boxborderw=22:"
        "x=(w-text_w)/2:y=110:line_spacing=12,"
        "fade=t=in:st=0:d=0.10,fade=t=out:st=5.90:d=0.10,format=yuv420p[v]"
    )
    audio_filter = (
        "aevalsrc=0.22*sin(2*PI*62*t)+0.09*sin(2*PI*124*t):s=44100:d=6,"
        "tremolo=f=4:d=0.82,highpass=f=45,lowpass=f=1600,"
        "afade=t=in:st=0:d=0.10,afade=t=out:st=5.75:d=0.25,"
        "volume=0.30,alimiter=limit=0.90[a]"
    )
    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
        "-filter_complex", f"{video_filter};{audio_filter}",
        "-map", "[v]", "-map", "[a]", "-t", "6",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output),
    ]
    try:
        subprocess.run(command, check=True, timeout=180)
    finally:
        source.unlink(missing_ok=True)
        caption_file.unlink(missing_ok=True)
    if output.stat().st_size < 10_000 or b"ftyp" not in output.read_bytes()[:64]:
        raise RuntimeError("FFmpeg did not produce a valid MP4")
    return output, {
        "title": f"{idea.title} #Shorts"[:100],
        "description": "#funny #meme #shorts #viral",
        "tags": ["funny", "meme", "shorts", "viral", "unexpected"],
        "attribution": attribution,
        "duration_seconds": 6,
        "loop": "ping-pong",
        "cached": False,
    }
