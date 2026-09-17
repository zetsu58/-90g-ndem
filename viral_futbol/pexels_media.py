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


def _commons_urls(query: str) -> list[tuple[str, str]]:
    params = urllib.parse.urlencode({"action":"query","generator":"search","gsrsearch":query,"gsrnamespace":"6","gsrlimit":"12","prop":"imageinfo","iiprop":"url|mime|extmetadata","iiurlwidth":"1200","format":"json","origin":"*"})
    request = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + params, headers={"User-Agent":"90Gundem/1.0 (football shorts)"})
    with urllib.request.urlopen(request, timeout=18) as response: payload = json.loads(response.read())
    required = [token for token in _normalized(query).split() if len(token)>2 and token not in {"football","logo","player"}]; matches=[]
    for page in (payload.get("query",{}).get("pages",{}) or {}).values():
        info=(page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime") or "").startswith("image/"): continue
        page_title=_normalized(str(page.get("title") or ""))
        if required and not all(token in page_title for token in required): continue
        url=info.get("thumburl") or info.get("url")
        if url: matches.append((str(url), str(page.get("title") or query)))
    return matches


def _media_score(title: str, media_title: str) -> int:
    story = set(_normalized(title).split()); media = set(_normalized(media_title).split()); entities = {_normalized(x) for x in _entities(title)}
    score = 0
    for entity in entities:
        tokens=set(entity.split())
        if tokens and tokens.issubset(media): score += 8
    score += min(5, len((story - STOP_WORDS) & media))
    if any(word in media for word in ("logo","crest","badge","emblem")): score += 2
    return score


def _search_relevant(title: str, limit: int) -> list[tuple[str,str]]:
    candidates=[]; club_keys={_normalized(club) for club in CLUBS}
    for entity in _entities(title):
        is_club=_normalized(entity) in club_keys
        for query in ((f"{entity} logo", f"{entity} football") if is_club else (f"{entity} football", entity)):
            try:
                for item in _commons_urls(query):
                    score=_media_score(title,item[1])
                    if score < 8: continue
                    candidates.append((score,item[0],item[1]))
            except Exception as exc: print(f"ViralFutbol Commons search deferred: {type(exc).__name__}: {exc}", flush=True)
    candidates.sort(key=lambda x:x[0], reverse=True); results=[]; seen=set()
    for _,url,credit in candidates:
        if url in seen: continue
        seen.add(url); results.append((url,credit))
        if len(results)>=limit: break
    return results


def _render_frame(photo_path: Path, output_path: Path, title: str, phrase: str, credit: str, index: int, total: int) -> None:
    with Image.open(photo_path) as opened: image=ImageOps.fit(opened.convert("RGB"),(1080,1920),method=Image.Resampling.LANCZOS)
    image=image.convert("RGBA"); shade=Image.new("RGBA",image.size,(0,0,0,0)); draw_shade=ImageDraw.Draw(shade)
    for y in range(1920):
        alpha=150-int(y*.35) if y<260 else (min(225,45+int((y-1090)*.48)) if y>545 else 35); draw_shade.line((0,y,1080,y),fill=(2,8,18,alpha))
    image=Image.alpha_composite(image,shade).convert("RGB"); draw=ImageDraw.Draw(image); accent="#ff2438"; draw.rounded_rectangle((44,36,1036,172),radius=16,fill="#050505",outline=accent,width=2)
    logo_path=Path(__file__).resolve().parents[1]/"assets"/"90gundem-logo-v2.png"
    if logo_path.exists():
        with Image.open(logo_path) as logo_opened: logo=ImageOps.contain(logo_opened.convert("RGBA"),(116,116),method=Image.Resampling.LANCZOS)
        image.paste(logo,(62,46),logo); draw=ImageDraw.Draw(image)
    draw.text((204,80),"SON DAKİKA  •  90+ GÜNDEM",font=_font(36,True),fill="white"); draw.rounded_rectangle((56,1260,680,1360),radius=15,fill=accent); draw.text((96,1288),_story_label(title),font=_font(18,True),fill="#06101c")
    display_text=title if index==0 else phrase; y=1420
    for line in _lines(display_text,29,4): draw.text((58,y),line,font=_font(60,True),fill="white",stroke_width=2,stroke_fill="#07111f"); y+=80
    draw.text((60,1800),"90+ Gündem  •  #Futbol #Shorts",font=_font(34,True),fill="#e7edf4")
    if credit and credit!="Pexels": draw.text((840,1816),"CC/Wikimedia",font=_font(22),fill="#c5d1df")
    bar_width=960//max(1,total)
    for slot in range(total): draw.rounded_rectangle((60+slot*bar_width,1860,60+slot*bar_width+bar_width-16,1880),radius=5,fill=accent if slot<=index else "#607086")
    image.save(output_path,"JPEG",quality=92,optimize=True)


def download_pexels_frames(*, title: str, narration: str, sources: list[str], output_dir: Path, story_id: str, limit: int = 8) -> list[Path]:
    del sources
    media=_search_relevant(title,limit); unique=[]
    for item in media:
        if item[0] not in {url for url,_ in unique}: unique.append(item)
        if len(unique)>=limit: break
    # Fail closed: if no entity-matched licensed image exists, let the branded
    # fallback card render instead of inserting unrelated stock footage.
    if not unique:
        print(f"ViralFutbol media gate: no relevant licensed image for {title!r}; using branded fallback", flush=True); return []
    phrases=[part.strip()+("?" if "?" in part else ".") for part in re.split(r"[.!?]+",narration) if part.strip()] or [title]
    frames=[]; selected=[unique[index%len(unique)] for index in range(max(5,len(unique)))]
    for index,(url,credit) in enumerate(selected[:limit]):
        raw_path=output_dir/f"{story_id}-media-{index}"; frame_path=output_dir/f"{story_id}-frame-{index}.jpg"
        try:
            request=urllib.request.Request(url,headers={"User-Agent":"90Gundem/1.0"})
            with urllib.request.urlopen(request,timeout=20) as response: raw=response.read(10_000_001)
            if len(raw)>10_000_000: continue
            raw_path.write_bytes(raw); _render_frame(raw_path,frame_path,title,phrases[index%len(phrases)],credit,index,len(selected[:limit])); frames.append(frame_path)
        except Exception as exc: print(f"ViralFutbol relevant image deferred: {type(exc).__name__}: {exc}", flush=True)
        finally: raw_path.unlink(missing_ok=True)
    return frames
