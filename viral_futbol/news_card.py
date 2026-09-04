from __future__ import annotations

import re
import textwrap
from pathlib import Path
from urllib.parse import urlparse


def _safe_name(title: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return (value[:48] or "news") + ".jpg"


def render_news_card(title: str, source_url: str, output_dir: str = "storage/x_cards") -> str:
    """Render a clean 1080x1350 news card without third-party logos."""
    from PIL import Image, ImageDraw, ImageFont

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    path = str(Path(output_dir) / _safe_name(title))
    image = Image.new("RGB", (1080, 1350), (245, 245, 245))
    draw = ImageDraw.Draw(image)

    def font(size: int, bold: bool = False):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        return ImageFont.load_default()

    draw.rectangle((0, 0, 1080, 170), fill=(20, 20, 20))
    draw.text((70, 48), "SON DAKİKA", font=font(62, True), fill=(255, 255, 255))
    draw.rectangle((70, 220, 1010, 230), fill=(20, 20, 20))

    clean = " ".join(title.split())
    lines = textwrap.wrap(clean, width=25)[:7]
    y = 310
    headline_font = font(66, True)
    for line in lines:
        draw.text((70, y), line, font=headline_font, fill=(18, 18, 18))
        y += 88

    host = urlparse(source_url).netloc.removeprefix("www.") or "kaynak"
    draw.text((70, 1160), f"Kaynak: {host}", font=font(34), fill=(80, 80, 80))
    draw.text((70, 1230), "GÜNDEM • ANLIK HABER", font=font(38, True), fill=(25, 25, 25))
    image.save(path, "JPEG", quality=92, optimize=True)
    return path
