from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont, ImageOps


def _font(size: int, bold: bool = False):
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _lines(text: str, width: int, maximum: int) -> list[str]:
    return wrap(re.sub(r"\s+", " ", text).strip(), width=width, break_long_words=False)[:maximum]


def _queries(title: str) -> list[str]:
    value = title.casefold()
    queries = []
    if "transfer" in value or "imza" in value:
        queries.extend(["football player signing", "football transfer press conference"])
    if "teknik direkt" in value or "hoca" in value:
        queries.append("football coach sideline")
    if "maç" in value or "gol" in value:
        queries.append("football match stadium")
    if "taraftar" in value or "derbi" in value:
        queries.append("football fans stadium")
    queries.extend(["professional football player", "football stadium lights", "football training"])
    return list(dict.fromkeys(queries))


def _search_urls(api_key: str, query: str) -> list[str]:
    params = urllib.parse.urlencode({
        "query": query,
        "orientation": "portrait",
        "size": "large",
        "per_page": "12",
    })
    request = urllib.request.Request(
        "https://api.pexels.com/v1/search?" + params,
        headers={"Authorization": api_key, "User-Agent": "90Gundem/1.0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
    urls = []
    for photo in payload.get("photos") or []:
        src = photo.get("src") or {}
        url = src.get("portrait") or src.get("large2x") or src.get("large")
        if url:
            urls.append(str(url))
    return urls


def _render_frame(photo_path: Path, output_path: Path, title: str, source: str, index: int, total: int) -> None:
    with Image.open(photo_path) as opened:
        image = ImageOps.fit(opened.convert("RGB"), (540, 960), method=Image.Resampling.LANCZOS)
    image = image.convert("RGBA")
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_shade = ImageDraw.Draw(shade)
    for y in range(960):
        if y < 130:
            alpha = 155 - int(y * 0.35)
        elif y > 545:
            alpha = min(225, 45 + int((y - 545) * 0.48))
        else:
            alpha = 35
        draw_shade.line((0, y, 540, y), fill=(2, 8, 18, alpha))
    image = Image.alpha_composite(image, shade).convert("RGB")
    draw = ImageDraw.Draw(image)
    accent = "#38e07b"
    draw.rounded_rectangle((22, 22, 518, 76), radius=16, fill="#07111fe8", outline=accent, width=2)
    draw.text((42, 36), "90+ GÜNDEM  •  SON DAKİKA", font=_font(20, True), fill=accent)

    label = ("HABERİN DETAYI", "TRANSFER GÜNDEMİ", "SAHADAN SICAK", "TARAFTAR NE DİYOR?", "SON DURUM", "HIZLI ÖZET")[index % 6]
    draw.rounded_rectangle((28, 630, 292, 680), radius=15, fill=accent)
    draw.text((48, 644), label, font=_font(18, True), fill="#06101c")

    y = 710
    for line in _lines(title, 27, 4):
        draw.text((29, y), line, font=_font(32, True), fill="white", stroke_width=2, stroke_fill="#07111f")
        y += 42

    draw.text((30, 900), ("Kaynak: " + source)[:55], font=_font(17), fill="#e7edf4")
    draw.text((380, 900), "Görsel: Pexels", font=_font(15), fill="#c5d1df")
    bar_width = 480 // max(1, total)
    for slot in range(total):
        color = accent if slot <= index else "#607086"
        draw.rounded_rectangle((30 + slot * bar_width, 930, 30 + slot * bar_width + bar_width - 8, 940), radius=5, fill=color)
    image.save(output_path, "JPEG", quality=88, optimize=True)


def download_pexels_frames(
    *, title: str, sources: list[str], output_dir: Path, story_id: str, limit: int = 6
) -> list[Path]:
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key:
        return []
    urls: list[str] = []
    try:
        for query in _queries(title):
            for url in _search_urls(api_key, query):
                if url not in urls:
                    urls.append(url)
                if len(urls) >= limit:
                    break
            if len(urls) >= limit:
                break
    except Exception as exc:
        print(f"ViralFutbol Pexels search deferred: {type(exc).__name__}: {exc}", flush=True)
        return []

    frames: list[Path] = []
    source = sources[0] if sources else "güncel yayın"
    headers = {"User-Agent": "90Gundem/1.0"}
    for index, url in enumerate(urls[:limit]):
        raw_path = output_dir / f"{story_id}-pexels-{index}.jpg"
        frame_path = output_dir / f"{story_id}-frame-{index}.jpg"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                continue
            raw_path.write_bytes(raw)
            _render_frame(raw_path, frame_path, title, source, index, min(limit, len(urls)))
            frames.append(frame_path)
        except Exception as exc:
            print(f"ViralFutbol Pexels image deferred: {type(exc).__name__}: {exc}", flush=True)
        finally:
            raw_path.unlink(missing_ok=True)
    return frames
