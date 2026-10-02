"""Landscape media and narration assets for autonomous long-form videos."""
from __future__ import annotations
import asyncio,html,json,os,re,subprocess,urllib.parse,urllib.request
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps

UA={"User-Agent":"90Gundem-BAMLOOP/1.0"}
ALLOWED_LICENSE=("cc by","cc0","public domain","pd-")

def _font(size:int,bold:bool=False):
    paths=("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
           "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path,size)
    return ImageFont.load_default()

def _plain(value:str)->str:
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",html.unescape(value or ""))).strip()

def _commons(query:str,limit:int=8)->list[dict]:
    params=urllib.parse.urlencode({"action":"query","generator":"search","gsrsearch":query,"gsrnamespace":"6","gsrlimit":str(max(4,limit*2)),
        "prop":"imageinfo","iiprop":"url|mime|extmetadata","iiurlwidth":"1600","format":"json","origin":"*"})
    req=urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+params,headers=UA)
    with urllib.request.urlopen(req,timeout=20) as response:
        data=json.loads(response.read())
    rows=[]
    for page in (data.get("query",{}).get("pages",{}) or {}).values():
        info=(page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime") or "").startswith("image/"):
            continue
        meta=info.get("extmetadata") or {}
        license_name=str((meta.get("LicenseShortName") or {}).get("value") or "")
        if license_name and not any(x in license_name.casefold() for x in ALLOWED_LICENSE):
            continue
        url=str(info.get("thumburl") or info.get("url") or "")
        if not url:
            continue
        rows.append({"url":url,"title":str(page.get("title") or query),
                     "license":license_name or "Wikimedia Commons",
                     "artist":_plain(str((meta.get("Artist") or {}).get("value") or "")),
                     "page":str(info.get("descriptionurl") or "")})
        if len(rows)>=limit:
            break
    return rows

def _download(url:str,path:Path)->None:
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=25) as response, path.open("wb") as out:
        total=0
        while True:
            chunk=response.read(1024*1024)
            if not chunk:
                break
            total+=len(chunk)
            if total>12*1024*1024:
                raise ValueError("commons_asset_too_large")
            out.write(chunk)

def _frame(source:Path,destination:Path,subject:str,label:str)->None:
    with Image.open(source) as opened:
        image=ImageOps.fit(opened.convert("RGB"),(1280,720),method=Image.Resampling.LANCZOS)
    overlay=Image.new("RGBA",image.size,(0,0,0,0))
    draw=ImageDraw.Draw(overlay)
    draw.rectangle((0,0,1280,100),fill=(0,0,0,125))
    draw.rectangle((0,560,1280,720),fill=(0,0,0,150))
    image=Image.alpha_composite(image.convert("RGBA"),overlay).convert("RGB")
    draw=ImageDraw.Draw(image)
    draw.text((42,28),subject[:72],font=_font(32,True),fill="white")
    draw.text((42,600),label[:110],font=_font(30,True),fill="white")
    image.save(destination,"JPEG",quality=91,optimize=True)

def _card(destination:Path,subject:str,claim:str,index:int)->None:
    image=Image.new("RGB",(1280,720),(8,17,31))
    draw=ImageDraw.Draw(image)
    draw.rectangle((0,0,1280,110),fill=(10,52,42))
    draw.text((48,30),"90+ GÜNDEM" if index%2==0 else "BİLGİ DOSYASI",font=_font(34,True),fill="white")
    draw.text((48,145),subject[:68],font=_font(46,True),fill="white")
    words=claim.split();lines=[];line=[]
    for word in words:
        if len(" ".join(line+[word]))>58:
            lines.append(" ".join(line));line=[word]
        else:
            line.append(word)
    if line: lines.append(" ".join(line))
    y=265
    for value in lines[:5]:
        draw.text((48,y),value,font=_font(32),fill=(235,241,248));y+=58
    draw.text((48,660),"Doğrulanmış kayıt • otomatik editoryal kart",font=_font(20),fill=(180,192,208))
    image.save(destination,"JPEG",quality=90,optimize=True)

def build_media(*,subject:str,scenes:list[dict],claims:list[str],output_dir:Path,content_id:str,limit:int=12)->tuple[list[Path],list[dict]]:
    output_dir.mkdir(parents=True,exist_ok=True)
    frames=[];credits=[];seen=set()
    queries=[]
    for scene in scenes:
        query=str(scene.get("visual_query") or subject).strip()
        if query and query not in queries:
            queries.append(query)
    queries.append(subject)
    for query in queries:
        if len(frames)>=limit:
            break
        try:
            candidates=_commons(query,3)
        except Exception as exc:
            print(f"Longform Commons deferred: {type(exc).__name__}",flush=True)
            continue
        for item in candidates:
            if len(frames)>=limit or item["url"] in seen:
                continue
            seen.add(item["url"])
            raw=output_dir/f"{content_id}-raw-{len(frames)}"
            frame=output_dir/f"{content_id}-frame-{len(frames)}.jpg"
            try:
                _download(item["url"],raw)
                label=str(scenes[len(frames)%len(scenes)].get("section") or subject) if scenes else subject
                _frame(raw,frame,subject,label)
                frames.append(frame);credits.append(item)
            except Exception as exc:
                print(f"Longform media asset deferred: {type(exc).__name__}",flush=True)
                frame.unlink(missing_ok=True)
            finally:
                raw.unlink(missing_ok=True)
    target=max(6,min(limit,max(6,len(scenes))))
    while len(frames)<target:
        index=len(frames);frame=output_dir/f"{content_id}-card-{index}.jpg"
        _card(frame,subject,claims[index%len(claims)] if claims else subject,index)
        frames.append(frame)
    return frames,credits

async def _edge(text:str,voice:str,path:Path)->None:
    import edge_tts
    rate=os.getenv("LONGFORM_TTS_RATE","+5%")
    pitch=os.getenv("LONGFORM_TTS_PITCH","+0Hz")
    await edge_tts.Communicate(text=text,voice=voice,rate=rate,pitch=pitch,volume="+8%").save(str(path))

def synthesize(text:str,path:Path,voice:str="tr-TR-EmelNeural")->Path:
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        asyncio.run(asyncio.wait_for(_edge(text,voice,path),timeout=max(60,int(os.getenv("LONGFORM_TTS_TIMEOUT_SECONDS","180")))))
    except Exception as exc:
        print(f"Longform Edge TTS unavailable, using offline voice: {type(exc).__name__}",flush=True)
        subprocess.run(["espeak-ng","-v","tr","-s","155","-w",str(path),text],check=True,timeout=240)
    if not path.exists() or path.stat().st_size<1024:
        raise RuntimeError("longform_tts_failed")
    return path
