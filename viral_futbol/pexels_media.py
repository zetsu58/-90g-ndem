from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

CLUBS = ("Galatasaray", "Fenerbahçe", "Beşiktaş", "Trabzonspor", "Başakşehir", "Real Madrid", "Barcelona", "Manchester City", "Manchester United", "Liverpool", "Arsenal", "Chelsea", "Bayern Münih", "Bayern Munich", "Paris Saint-Germain", "PSG", "Juventus", "Inter", "Milan", "Napoli")
STOP_WORDS = {"son", "dakika", "yeni", "transfer", "futbol", "haber", "gundem", "sicak", "ayrilik", "plani", "yapilacak", "resmi", "aciklama", "iddiasi", "icin"}
ALLOWED_LICENSE = ("cc by", "cc0", "public domain", "pd-")
UNRELATED_SUBJECTS = ("fan boy", "supporter", "cosplay", "video game", "fifa 2", "football manager", "montage", "meme")


def _font(size: int, bold: bool = False):
    names = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")
    for name in names:
        if Path(name).exists(): return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _lines(text: str, width: int, maximum: int) -> list[str]: return wrap(re.sub(r"\s+", " ", text).strip(), width=width, break_long_words=False)[:maximum]

def _normalized(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode(); return re.sub(r"[^a-z0-9]+", " ", plain).strip()


def _entities(title: str) -> list[str]:
    found = [club for club in CLUBS if _normalized(club) in _normalized(title)]; remainder = title
    for club in found: remainder = re.sub(re.escape(club), " ", remainder, flags=re.IGNORECASE)
    proper = re.findall(r"\b[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+){0,1}", remainder)
    for item in proper:
        if _normalized(item) not in STOP_WORDS and item not in found: found.append(item)
    return found[:4]


def _story_label(title: str) -> str:
    value = title.casefold()
    if any(word in value for word in ("transfer", "imza", "ayrılık")): return "TRANSFER GELİŞMESİ"
    if "teknik direkt" in value or "hoca" in value: return "TEKNİK DİREKTÖR"
    if "sakat" in value: return "SAKATLIK HABERİ"
    if any(word in value for word in ("maç", "derbi", "gol")): return "MAÇ GÜNDEMİ"
    return "FUTBOL GÜNDEMİ"


def _commons_urls(query: str) -> list[dict]:
    params = urllib.parse.urlencode({"action":"query","generator":"search","gsrsearch":query,"gsrnamespace":"6","gsrlimit":"24","prop":"imageinfo","iiprop":"url|size|mime|extmetadata","iiurlwidth":"1600","format":"json"})
    request = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + params, headers={"User-Agent":"90Gundem/1.0 (football shorts)"})
    with urllib.request.urlopen(request, timeout=18) as response: payload = json.loads(response.read())
    required = " ".join(token for token in _normalized(query).split() if len(token)>2 and token not in {"football","logo","player"}); matches=[]
    for page in (payload.get("query",{}).get("pages",{}) or {}).values():
        info=(page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime") or "").startswith("image/"): continue
        meta=info.get("extmetadata") or {}
        license_name=str((meta.get("LicenseShortName") or {}).get("value") or "")
        if not any(value in license_name.casefold() for value in ALLOWED_LICENSE): continue
        if min(int(info.get("width") or 0),int(info.get("height") or 0))<600: continue
        page_title=_normalized(str(page.get("title") or ""))
        if required and required not in page_title: continue
        if any(term in page_title for term in UNRELATED_SUBJECTS): continue
        url=info.get("thumburl") or info.get("url")
        if url:
            artist=re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",str((meta.get("Artist") or {}).get("value") or ""))).strip()
            matches.append({"url":str(url),"title":str(page.get("title") or query),
                            "artist":artist[:160] or "Wikimedia contributor","license":license_name,
                            "page":str(info.get("descriptionurl") or "")})
    return matches


def _media_score(title: str, media_title: str) -> int:
    story = set(_normalized(title).split()); media = set(_normalized(media_title).split()); entities = {_normalized(x) for x in _entities(title)}
    score = 0
    for entity in entities:
        tokens=set(entity.split())
        if tokens and tokens.issubset(media): score += 8
        if len(tokens)>1 and entity in _normalized(media_title): score += 4
    score += min(5, len((story - STOP_WORDS) & media))
    if any(word in media for word in ("logo","crest","badge","emblem")):
        score -= 2 if any(len(entity.split())>1 for entity in entities) else 1
    return score


def _search_relevant(title: str, limit: int) -> list[dict]:
    candidates=[]; club_keys={_normalized(club) for club in CLUBS}
    for entity in _entities(title):
        is_club=_normalized(entity) in club_keys
        for query in ((entity, f"{entity} football", f"{entity} logo") if is_club else (entity, f"{entity} football")):
            try:
                for item in _commons_urls(query):
                    score=_media_score(title,item["title"])
                    if score < 8: continue
                    candidates.append((score,item))
            except Exception as exc: print(f"ViralFutbol Commons search deferred: {type(exc).__name__}", flush=True)
    candidates.sort(key=lambda x:x[0], reverse=True); results=[]; seen=set()
    for _,item in candidates:
        if item["url"] in seen: continue
        seen.add(item["url"]); results.append(item)
        if len(results)>=limit: break
    return results


def _render_frame(photo_path: Path, output_path: Path, title: str, phrase: str, credit: str, index: int, total: int) -> None:
    with Image.open(photo_path) as opened:
        original=opened.convert("RGB")
        # Keep the complete subject visible. Landscape news photos otherwise
        # lose the player when center-cropped into a portrait Short.
        image=ImageOps.fit(original,(1080,1920),method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(48))
        foreground=ImageOps.contain(original,(1020,1390),method=Image.Resampling.LANCZOS)
        image.paste(foreground,((1080-foreground.width)//2,(1920-foreground.height)//2-80))
    image=image.convert("RGBA"); shade=Image.new("RGBA",image.size,(0,0,0,0)); draw_shade=ImageDraw.Draw(shade)
    for y in range(1920):
        alpha=150-int(y*.35) if y<260 else (min(225,45+int((y-1090)*.48)) if y>545 else 35); draw_shade.line((0,y,1080,y),fill=(2,8,18,alpha))
    image=Image.alpha_composite(image,shade).convert("RGB"); draw=ImageDraw.Draw(image); accent="#ff2438"; draw.rounded_rectangle((44,36,1036,172),radius=16,fill="#050505",outline=accent,width=2)
    logo_path=Path(__file__).resolve().parents[1]/"assets"/"90gundem-logo-v2.png"
    if logo_path.exists():
        try:
            with Image.open(logo_path) as logo_opened: logo=ImageOps.contain(logo_opened.convert("RGBA"),(116,116),method=Image.Resampling.LANCZOS)
            image.paste(logo,(62,46),logo); draw=ImageDraw.Draw(image)
        except (OSError, ValueError):
            print("ViralFutbol optional logo unavailable", flush=True)
    draw.text((204,80),"SON DAKİKA  •  90+ GÜNDEM",font=_font(36,True),fill="white"); draw.rounded_rectangle((56,1260,680,1360),radius=15,fill=accent); draw.text((96,1288),_story_label(title),font=_font(18,True),fill="#06101c")
    display_text=title if index==0 else phrase; y=1530
    for line in _lines(display_text,31,2): draw.text((58,y),line,font=_font(54,True),fill="white",stroke_width=2,stroke_fill="#07111f"); y+=76
    draw.text((60,1800),"90+ Gündem  •  #Futbol #Shorts",font=_font(34,True),fill="#e7edf4")
    if credit and credit!="Pexels": draw.text((840,1816),"CC/Wikimedia",font=_font(22),fill="#c5d1df")
    bar_width=960//max(1,total)
    for slot in range(total): draw.rounded_rectangle((60+slot*bar_width,1860,60+slot*bar_width+bar_width-16,1880),radius=5,fill=accent if slot<=index else "#607086")
    image.save(output_path,"JPEG",quality=92,optimize=True)


def download_pexels_frames(*, title: str, narration: str, sources: list[str], output_dir: Path, story_id: str, limit: int = 8) -> list[Path]:
    del sources
    media=_search_relevant(title,limit); unique=[]
    for item in media:
        if item["url"] not in {candidate["url"] for candidate in unique}: unique.append(item)
        if len(unique)>=limit: break
    if len(unique)<2:
        print("ViralFutbol media gate: insufficient relevant licensed imagery", flush=True); return []
    phrases=[part.strip()+("?" if "?" in part else ".") for part in re.split(r"[.!?]+",narration) if part.strip()] or [title]
    frames=[]; selected=unique[:limit]
    credits=[]
    for index,item in enumerate(selected[:limit]):
        raw_path=output_dir/f"{story_id}-media-{index}"; frame_path=output_dir/f"{story_id}-frame-{index}.jpg"
        try:
            request=urllib.request.Request(item["url"],headers={"User-Agent":"90Gundem/2.0 (https://viralfutbol.onrender.com/about)"})
            with urllib.request.urlopen(request,timeout=20) as response: raw=response.read(10_000_001)
            if len(raw)>10_000_000: continue
            raw_path.write_bytes(raw); _render_frame(raw_path,frame_path,title,phrases[index%len(phrases)],item["title"],index,len(selected[:limit])); frames.append(frame_path); credits.append(item)
        except Exception as exc: print(f"ViralFutbol relevant image deferred: {type(exc).__name__}", flush=True)
        finally: raw_path.unlink(missing_ok=True)
    if len(frames)<2:
        for frame in frames: frame.unlink(missing_ok=True)
        return []
    (output_dir/f"{story_id}-media-credits.json").write_text(json.dumps(credits,ensure_ascii=False),encoding="utf-8")
    return frames
