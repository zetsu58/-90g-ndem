from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont, ImageOps

CLUBS = ("Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Başakşehir", "Real Madrid", "Barcelona", "Manchester City", "Manchester United", "Liverpool", "Arsenal", "Chelsea", "Bayern Münih", "Bayern Munich", "Paris Saint-Germain", "PSG", "Juventus", "Inter", "Milan", "Napoli")
STOP_WORDS = {"son", "dakika", "yeni", "transfer", "futbol", "haber", "gundem", "sicak", "ayrilik", "plani", "yapilacak", "resmi", "aciklama", "iddiasi", "icin"}


def _font(size: int, bold: bool = False):
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _lines(text: str, width: int, maximum: int) -> list[str]:
    return wrap(re.sub(r"\s+", " ", text).strip(), width=width, break_long_words=False)[:maximum]


def _normalized(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def _entities(title: str) -> list[str]:
    found = [club for club in CLUBS if _normalized(club) in _normalized(title)]
    proper = re.findall(r"\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){0,2}", title)
    for item in proper:
        if _normalized(item) not in STOP_WORDS and item not in found:
            found.append(item)
    return found[:4]


def _story_label(title: str) -> str:
    value = title.casefold()
    if any(word in value for word in ("transfer", "imza", "ayrılık")):
        return "TRANSFER GELİŞMESİ"
    if "teknik direkt" in value or "hoca" in value:
        return "TEKNİK DİREKTÖR"
    if "sakat" in value:
        return "SAKATLIK HABERİ"
    if any(word in value for word in ("maç", "derbi", "gol")):
        return "MAÇ GÜNDEMİ"
    return "FUTBOL GÜNDEMİ"


def _commons_urls(query: str) -> list[tuple[str, str]]:
    params = urllib.parse.urlencode({"action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": "6", "gsrlimit": "12", "prop": "imageinfo", "iiprop": "url|mime|extmetadata", "iiurlwidth": "1200", "format": "json", "origin": "*"})
    request = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + params, headers={"User-Agent": "90Gundem/1.0 (football shorts)"})
    with urllib.request.urlopen(request, timeout=18) as response:
        payload = json.loads(response.read())
    required = [token for token in _normalized(query).split() if len(token) > 2 and token not in {"football", "logo", "player"}]
    matches: list[tuple[str, str]] = []
    for page in (payload.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime") or "").startswith("image/"):
            continue
        if required and not any(token in _normalized(str(page.get("title") or "")) for token in required):
            continue
        url = info.get("thumburl") or info.get("url")
        if url:
            matches.append((str(url), str(page.get("title") or query)))
    return matches


def _search_relevant(title: str, limit: int) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    for entity in _entities(title):
        for query in (entity, f"{entity} football", f"{entity} logo"):
            try:
                for item in _commons_urls(query):
                    if item[0] not in {url for url, _ in results}:
                        results.append(item)
                    if len(results) >= limit:
                        return results
            except Exception as exc:
                print(f"ViralFutbol Commons search deferred: {type(exc).__name__}: {exc}", flush=True)
    return results


def _search_pexels(api_key: str, query: str) -> list[tuple[str, str]]:
    params = urllib.parse.urlencode({"query": query, "orientation": "portrait", "size": "large", "per_page": "6"})
    request = urllib.request.Request("https://api.pexels.com/v1/search?" + params, headers={"Authorization": api_key, "User-Agent": "90Gundem/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
    output = []
    for photo in payload.get("photos") or []:
        src = photo.get("src") or {}
        url = src.get("portrait") or src.get("large2x") or src.get("large")
        if url:
            output.append((str(url), "Pexels"))
    return output


def _render_frame(photo_path: Path, output_path: Path, title: str, phrase: str, credit: str, index: int, total: int) -> None:
    with Image.open(photo_path) as opened:
        image = ImageOps.fit(opened.convert("RGB"), (540, 960), method=Image.Resampling.LANCZOS)
    image = image.convert("RGBA")
    shade = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw_shade = ImageDraw.Draw(shade)
    for y in range(960):
        alpha = 150 - int(y * .35) if y < 130 else (min(225, 45 + int((y - 545) * .48)) if y > 545 else 35)
        draw_shade.line((0, y, 540, y), fill=(2, 8, 18, alpha))
    image = Image.alpha_composite(image, shade).convert("RGB")
    draw = ImageDraw.Draw(image)
    accent = "#38e07b"
    draw.rounded_rectangle((22, 22, 518, 76), radius=16, fill="#07111f", outline=accent, width=2)
    draw.text((42, 36), "90+ GÜNDEM  •  SON DAKİKA", font=_font(20, True), fill=accent)
    draw.rounded_rectangle((28, 630, 340, 680), radius=15, fill=accent)
    draw.text((48, 644), _story_label(title), font=_font(18, True), fill="#06101c")
    display_text = title if index == 0 else phrase
    y = 710
    for line in _lines(display_text, 29, 4):
        draw.text((29, y), line, font=_font(30, True), fill="white", stroke_width=2, stroke_fill="#07111f")
        y += 40
    draw.text((30, 900), "90+ Gündem  •  #Futbol #Shorts", font=_font(17, True), fill="#e7edf4")
    if credit and credit != "Pexels":
        draw.text((420, 908), "CC/Wikimedia", font=_font(11), fill="#c5d1df")
    bar_width = 480 // max(1, total)
    for slot in range(total):
        color = accent if slot <= index else "#607086"
        draw.rounded_rectangle((30 + slot * bar_width, 930, 30 + slot * bar_width + bar_width - 8, 940), radius=5, fill=color)
    image.save(output_path, "JPEG", quality=88, optimize=True)


def download_pexels_frames(*, title: str, narration: str, sources: list[str], output_dir: Path, story_id: str, limit: int = 8) -> list[Path]:
    del sources
    media = _search_relevant(title, limit)
    if len(media) < 2:
        api_key = os.getenv("PEXELS_API_KEY", "").strip()
        entities = _entities(title)
        if api_key and entities:
            try:
                media.extend(_search_pexels(api_key, entities[0] + " football"))
            except Exception as exc:
                print(f"ViralFutbol Pexels search deferred: {type(exc).__name__}: {exc}", flush=True)
    unique: list[tuple[str, str]] = []
    for item in media:
        if item[0] not in {url for url, _ in unique}:
            unique.append(item)
        if len(unique) >= limit:
            break
    phrases = [part.strip() + ("?" if "?" in part else ".") for part in re.split(r"[.!?]+", narration) if part.strip()] or [title]
    frames: list[Path] = []
    for index, (url, credit) in enumerate(unique):
        raw_path = output_dir / f"{story_id}-media-{index}"
        frame_path = output_dir / f"{story_id}-frame-{index}.jpg"
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "90Gundem/1.0"})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                continue
            raw_path.write_bytes(raw)
            _render_frame(raw_path, frame_path, title, phrases[index % len(phrases)], credit, index, len(unique))
            frames.append(frame_path)
        except Exception as exc:
            print(f"ViralFutbol relevant image deferred: {type(exc).__name__}: {exc}", flush=True)
        finally:
            raw_path.unlink(missing_ok=True)
    return frames
