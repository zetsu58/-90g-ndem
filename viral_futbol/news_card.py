from __future__ import annotations

import html
import textwrap
from pathlib import Path


def build_news_card_svg(title: str, output_path: str, *, brand: str = "VIRAL FUTBOL") -> str:
    """Generate a 1080x1350 news card as SVG without external dependencies."""
    clean = " ".join(title.split())
    lines = textwrap.wrap(clean, width=27)[:7] or ["Son Dakika"]
    if len(textwrap.wrap(clean, width=27)) > 7:
        lines[-1] = lines[-1].rstrip("…") + "…"
    text_nodes = "\n".join(
        f'<text x="80" y="{440 + i * 105}" font-size="72" font-family="Arial, sans-serif" font-weight="700" fill="white">{html.escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1350" viewBox="0 0 1080 1350">
<rect width="1080" height="1350" fill="#111111"/>
<rect x="0" y="0" width="1080" height="210" fill="#d71920"/>
<text x="80" y="135" font-size="72" font-family="Arial, sans-serif" font-weight="800" fill="white">{html.escape(brand)}</text>
<text x="80" y="330" font-size="42" font-family="Arial, sans-serif" font-weight="700" fill="#ffcf33">SON DAKİKA</text>
{text_nodes}
<text x="80" y="1260" font-size="34" font-family="Arial, sans-serif" fill="#bbbbbb">viral futbol • doğrulanmış futbol gündemi</text>
</svg>'''
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
    return str(path)
