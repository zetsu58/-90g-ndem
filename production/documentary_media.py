"""Documentary-grade long-form media acquisition and visual beat planning."""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

UA={"User-Agent":"90GundemMediaBot/2.1 (https://viralfutbol.onrender.com/)",
    "Api-User-Agent":"90GundemMediaBot/2.1 (https://viralfutbol.onrender.com/)"}
ALLOWED_LICENSE=("cc by","cc0","public domain","pd-")
UNRELATED_SUBJECTS=("fan boy","supporter","cosplay","video game","football manager","meme")
CONTEXT_CLUBS=("Fenerbahçe","Real Madrid","Galatasaray","Beşiktaş","Trabzonspor","Barcelona","Liverpool","Manchester City","Bayern Munich","Inter","Milan","Juventus","Arsenal","Chelsea")
STADIUM_WORDS=("stadium","stadyum","bernabeu","saracoglu","camp nou","anfield","etihad")

def _normalized(value:str)->str:
    plain=unicodedata.normalize("NFKD",str(value).casefold()).encode("ascii","ignore").decode()
    return re.sub(r"[^a-z0-9]+"," ",plain).strip()

def _tokens(value:str)->set[str]:
    return {x for x in _normalized(value).split() if len(x)>2 and x not in {"football","futbol","video","story","history","career"}}

def _proper_entities(text:str)->list[str]:
    values=re.findall(r"\b[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ.-]+(?:\s+[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ.-]+){0,2}",text)
    out=[]
    for item in values:
        item=re.sub(r"\s+"," ",item).strip(" .,:;")
        if len(item)>2 and item not in out:
            out.append(item)
    return out[:8]

def _commons(query:str,subject:str,limit:int=6)->list[dict]:
    params=urllib.parse.urlencode({
        "action":"query","generator":"search","gsrsearch":query,"gsrnamespace":"6",
        "gsrlimit":str(max(8,limit*3)),"prop":"imageinfo",
        "iiprop":"url|size|mime|extmetadata","iiurlwidth":"1600","format":"json"
    })
    req=urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+params,headers=UA)
    with urllib.request.urlopen(req,timeout=20) as response:
        data=json.loads(response.read())
    subject_tokens=_tokens(subject)
    rows=[]
    for page in (data.get("query",{}).get("pages",{}) or {}).values():
        info=(page.get("imageinfo") or [{}])[0]
        if not str(info.get("mime") or "").startswith("image/"):
            continue
        if int(info.get("width") or 0)<960 or int(info.get("height") or 0)<540:
            continue
        meta=info.get("extmetadata") or {}
        license_name=str((meta.get("LicenseShortName") or {}).get("value") or "")
        if not any(x in license_name.casefold() for x in ALLOWED_LICENSE):
            continue
        title=str(page.get("title") or "")
        if "stadium" in query.casefold() and not any(word in _normalized(title) for word in STADIUM_WORDS):
            continue
        title_tokens=_tokens(title)
        overlap=len(subject_tokens & title_tokens)
        # Subject-specific Commons results must visibly identify the documentary subject.
        if any(term in _normalized(title) for term in UNRELATED_SUBJECTS):
            continue
        if subject_tokens and overlap<min(2,len(subject_tokens)):
            continue
        url=str(info.get("thumburl") or info.get("url") or "")
        if not url:
            continue
        score=overlap*10 + min(5,len(_tokens(query)&title_tokens))
        rows.append({
            "url":url,"title":title,"score":score,"source":"Wikimedia Commons",
            "license":license_name or "Wikimedia Commons",
            "artist":re.sub(r"<[^>]+>"," ",str((meta.get("Artist") or {}).get("value") or "")).strip(),
            "page":str(info.get("descriptionurl") or ""),
        })
    rows.sort(key=lambda x:x["score"],reverse=True)
    return rows[:limit]


def _commons_video(query:str,subject:str,limit:int=3)->list[dict]:
    params=urllib.parse.urlencode({
        "action":"query","generator":"search","gsrsearch":query,"gsrnamespace":"6",
        "gsrlimit":str(max(8,limit*4)),"prop":"imageinfo",
        "iiprop":"url|mime|extmetadata","format":"json","origin":"*"
    })
    req=urllib.request.Request("https://commons.wikimedia.org/w/api.php?"+params,headers=UA)
    with urllib.request.urlopen(req,timeout=20) as response:
        data=json.loads(response.read())
    subject_tokens=_tokens(subject);rows=[]
    for page in (data.get("query",{}).get("pages",{}) or {}).values():
        info=(page.get("imageinfo") or [{}])[0]
        mime=str(info.get("mime") or "")
        if not (mime.startswith("video/") or mime in {"application/ogg"}):
            continue
        meta=info.get("extmetadata") or {}
        license_name=str((meta.get("LicenseShortName") or {}).get("value") or "")
        if not any(x in license_name.casefold() for x in ALLOWED_LICENSE):
            continue
        title=str(page.get("title") or "")
        title_tokens=_tokens(title)
        overlap=len(subject_tokens & title_tokens)
        if subject_tokens and overlap==0:
            continue
        url=str(info.get("url") or "")
        if not url:
            continue
        rows.append({
            "url":url,"title":title,"score":overlap*10,
            "source":"Wikimedia Commons","license":license_name or "Wikimedia Commons",
            "artist":re.sub(r"<[^>]+>"," ",str((meta.get("Artist") or {}).get("value") or "")).strip(),
            "page":str(info.get("descriptionurl") or ""),"mime":mime,
        })
    rows.sort(key=lambda x:x["score"],reverse=True)
    return rows[:limit]

def _pexels(query:str,limit:int=5)->list[dict]:
    key=os.getenv("PEXELS_API_KEY","").strip()
    if not key:
        return []
    params=urllib.parse.urlencode({"query":query,"per_page":str(max(5,limit)),"orientation":"landscape","size":"medium"})
    req=urllib.request.Request("https://api.pexels.com/v1/videos/search?"+params,headers={"Authorization":key,"User-Agent":UA["User-Agent"]})
    with urllib.request.urlopen(req,timeout=20) as response:
        data=json.loads(response.read())
    rows=[]
    for video in data.get("videos") or []:
        files=[
            item for item in (video.get("video_files") or [])
            if str(item.get("file_type") or "")=="video/mp4"
            and int(item.get("width") or 0)>=960 and int(item.get("height") or 0)>=540
        ]
        files.sort(key=lambda x:abs(int(x.get("width") or 0)-1280))
        if not files:
            continue
        rows.append({
            "url":str(files[0].get("link") or ""),
            "title":query,
            "source":"Pexels",
            "license":"Pexels License",
            "artist":str((video.get("user") or {}).get("name") or "Pexels"),
            "page":str(video.get("url") or ""),
        })
        if len(rows)>=limit:
            break
    return rows

def _download(url:str,path:Path,max_bytes:int)->None:
    req=urllib.request.Request(url,headers=UA)
    with urllib.request.urlopen(req,timeout=30) as response, path.open("wb") as out:
        total=0
        while True:
            chunk=response.read(1024*1024)
            if not chunk:
                break
            total+=len(chunk)
            if total>max_bytes:
                raise ValueError("documentary_asset_too_large")
            out.write(chunk)

def _normalize_archive_video(source:Path,destination:Path)->Path:
    subprocess.run([
        "ffmpeg","-y","-loglevel","error","-i",str(source),"-an",
        "-vf","scale='min(1280,iw)':-2:force_original_aspect_ratio=decrease,fps=30,format=yuv420p",
        "-c:v","libx264","-preset","veryfast","-crf","21","-movflags","+faststart",str(destination)
    ],check=True,timeout=max(90,int(os.getenv("LONGFORM_ARCHIVE_TRANSCODE_TIMEOUT_SECONDS","300"))))
    if not destination.exists() or destination.stat().st_size<100000:
        raise ValueError("documentary_archive_transcode")
    return destination

def _clean_image(source:Path,destination:Path)->None:
    with Image.open(source) as opened:
        image=ImageOps.fit(opened.convert("RGB"),(1280,720),method=Image.Resampling.LANCZOS)
        image.save(destination,"JPEG",quality=92,optimize=True)

def _image_fingerprint(path:Path)->str:
    with Image.open(path) as opened:
        small=ImageOps.fit(opened.convert("L"),(17,16),method=Image.Resampling.BILINEAR)
        pixels=list(small.getdata())
    bits=[]
    for row in range(16):
        base=row*17
        for col in range(16):
            bits.append("1" if pixels[base+col]>pixels[base+col+1] else "0")
    return hex(int("".join(bits),2))[2:]

def _scene_context(section:str,channel:str)->str:
    section=section.casefold()
    if channel=="viral_futbol":
        mapping={
            "hook":"football stadium crowd",
            "origins":"football youth training academy",
            "rise":"football training match stadium",
            "turning_points":"football transfer press conference stadium",
            "legacy_now":"football fans trophy stadium",
            "outro":"football stadium night fans",
        }
    else:
        mapping={
            "hook":"cinematic technology close up",
            "what":"technology laboratory close up",
            "how":"engineering mechanism technology",
            "examples":"technology real world usage",
            "takeaway":"technology future city",
            "outro":"cinematic technology abstract",
        }
    return mapping.get(section,"football documentary" if channel=="viral_futbol" else "technology documentary")

def _commons_queries(subject:str,scenes:list[dict],claims:list[str],channel:str)->list[str]:
    queries=[subject]
    if channel=="viral_futbol":
        queries.extend([f"{subject} football",f"{subject} stadium",f"{subject} team"])
    else:
        queries.extend([f"{subject} technology",f"{subject} diagram",f"{subject} science"])
    for claim in claims[:10]:
        for entity in _proper_entities(claim):
            if _normalized(subject) not in _normalized(entity) and len(entity)>3:
                queries.append(f"{subject} {entity}")
    for scene in scenes[:6]:
        section=str(scene.get("section") or "")
        if section:
            queries.append(f"{subject} {section.replace('_',' ')}")
    return list(dict.fromkeys(q.strip() for q in queries if q.strip()))[:14]

def _broll_queries(scenes:list[dict],channel:str)->list[str]:
    return list(dict.fromkeys(_scene_context(str(scene.get("section") or ""),channel) for scene in scenes))[:8]

def build_documentary_media(*,subject:str,scenes:list[dict],claims:list[str],output_dir:Path,
                            content_id:str,channel:str,target_assets:int|None=None)->dict:
    output_dir.mkdir(parents=True,exist_ok=True)
    target=max(8,target_assets or int(os.getenv("LONGFORM_MEDIA_TARGET","12")))
    min_real=max(6,int(os.getenv("LONGFORM_MIN_REAL_MEDIA","8")))
    min_video=max(0,int(os.getenv("LONGFORM_MIN_VIDEO_BROLL","0" if channel=="viral_futbol" else "2")))
    min_subject_images=max(1,int(os.getenv("LONGFORM_MIN_SUBJECT_IMAGES","1"))) if channel=="viral_futbol" else 0
    max_images=max(1,target-min_video)
    media=[];credits=[];fingerprints=set();urls=set();image_count=0;subject_image_count=0;video_count=0
    scene_media={str(i):[] for i in range(len(scenes))}

    def add_commons(item:dict,*,subject_photo:bool=True)->int|None:
        nonlocal image_count,subject_image_count
        if item["url"] in urls or len(media)>=target:
            return None
        raw=output_dir/f"{content_id}-commons-raw-{len(media)}"
        final=output_dir/f"{content_id}-doc-{len(media)}.jpg"
        try:
            _download(item["url"],raw,14*1024*1024)
            _clean_image(raw,final)
            fingerprint=_image_fingerprint(final)
            if fingerprint in fingerprints:
                final.unlink(missing_ok=True)
                return None
            fingerprints.add(fingerprint);urls.add(item["url"])
            media.append(final);credits.append(item);image_count+=1
            if subject_photo: subject_image_count+=1
            return len(media)-1
        except Exception as exc:
            print(f"Documentary Commons asset deferred: {type(exc).__name__}",flush=True)
            final.unlink(missing_ok=True)
            return None
        finally:
            raw.unlink(missing_ok=True)

    for query in _commons_queries(subject,scenes,claims,channel):
        if image_count>=max_images:
            break
        try:
            for item in _commons(query,subject,4):
                media_index=add_commons(item)
                if media_index is not None:
                    for values in scene_media.values():
                        values.append(media_index)
                if image_count>=max_images:
                    break
        except Exception as exc:
            print(f"Documentary Commons search deferred: {type(exc).__name__}",flush=True)

    # Use verified career teams for contextual stadium footage when the player
    # has too few distinct licensed portraits. Stadiums are real story locations.
    if channel=="viral_futbol" and image_count<max_images:
        verified_text=_normalized(" ".join(claims))
        for club in CONTEXT_CLUBS:
            if image_count>=max_images: break
            if _normalized(club) not in verified_text: continue
            try:
                for item in _commons(f"{club} stadium",club,4):
                    add_commons(item,subject_photo=False)
                    if image_count>=max_images: break
            except Exception as exc:
                print(f"Documentary context search deferred: {type(exc).__name__}",flush=True)

    # Prefer subject-specific licensed archival motion from Wikimedia Commons.
    for query in _commons_queries(subject,scenes,claims,channel)[:6]:
        if video_count>=min_video:
            break
        try:
            rows=_commons_video(query,subject,2)
        except Exception as exc:
            print(f"Documentary Commons video search deferred: {type(exc).__name__}",flush=True)
            rows=[]
        for item in rows:
            if not item["url"] or item["url"] in urls or video_count>=min_video:
                continue
            raw=output_dir/f"{content_id}-archive-raw-{len(media)}"
            final=output_dir/f"{content_id}-archive-{len(media)}.mp4"
            try:
                _download(item["url"],raw,48*1024*1024)
                probe=subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height",
                                      "-of","json",str(raw)],capture_output=True,text=True,timeout=25,check=True)
                streams=json.loads(probe.stdout or "{}").get("streams") or []
                video=next((x for x in streams if x.get("codec_type")=="video"),None)
                if not video or int(video.get("width") or 0)<640 or int(video.get("height") or 0)<360:
                    raise ValueError("documentary_archive_resolution")
                _normalize_archive_video(raw,final)
                urls.add(item["url"]);media.append(final);credits.append(item);video_count+=1
                media_index=len(media)-1
                for values in scene_media.values():
                    values.insert(0,media_index)
            except Exception as exc:
                print(f"Documentary Commons video deferred: {type(exc).__name__}",flush=True)
                final.unlink(missing_ok=True)
            finally:
                raw.unlink(missing_ok=True)

    # Contextual Pexels motion B-roll complements subject-specific archive/still imagery.
    for query in _broll_queries(scenes,channel):
        if len(media)>=target and video_count>=min_video:
            break
        try:
            rows=_pexels(query,2)
        except Exception as exc:
            print(f"Documentary Pexels search deferred: {type(exc).__name__}",flush=True)
            rows=[]
        for item in rows:
            if not item["url"] or item["url"] in urls or (len(media)>=target and video_count>=min_video):
                continue
            final=output_dir/f"{content_id}-broll-{len(media)}.mp4"
            try:
                _download(item["url"],final,32*1024*1024)
                # Reject obviously broken files before the render stage.
                probe=subprocess.run(["ffprobe","-v","error","-show_entries","stream=codec_type,width,height",
                                      "-of","json",str(final)],capture_output=True,text=True,timeout=20,check=True)
                streams=json.loads(probe.stdout or "{}").get("streams") or []
                video=next((x for x in streams if x.get("codec_type")=="video"),None)
                if not video or int(video.get("width") or 0)<960 or int(video.get("height") or 0)<540:
                    raise ValueError("documentary_broll_resolution")
                urls.add(item["url"]);media.append(final);credits.append(item);video_count+=1
                media_index=len(media)-1
                for scene_index,scene in enumerate(scenes):
                    if _scene_context(str(scene.get("section") or ""),channel)==query:
                        scene_media[str(scene_index)].insert(0,media_index)
            except Exception as exc:
                print(f"Documentary Pexels asset deferred: {type(exc).__name__}",flush=True)
                final.unlink(missing_ok=True)

    if len(media)<min_real:
        for path in media:
            Path(path).unlink(missing_ok=True)
        raise ValueError(f"documentary_real_media_gate:{len(media)}/{min_real}")
    if subject_image_count<min_subject_images:
        for path in media:
            Path(path).unlink(missing_ok=True)
        raise ValueError(f"documentary_subject_media_gate:{subject_image_count}/{min_subject_images}")
    if video_count<min_video:
        for path in media:
            Path(path).unlink(missing_ok=True)
        raise ValueError(f"documentary_motion_media_gate:{video_count}/{min_video}")

    return {
        "media":media,
        "credits":credits,
        "scene_media":scene_media,
        "report":{
            "real_media":len(media),"images":image_count,"subject_images":subject_image_count,"videos":video_count,
            "min_real_media":min_real,"min_video_broll":min_video,"min_subject_images":min_subject_images,"text_cards":0,
            "commons_queries":len(_commons_queries(subject,scenes,claims,channel)),
            "broll_queries":len(_broll_queries(scenes,channel)),
        },
    }

def visual_beats(scenes:list[dict],media_count:int,beat_seconds:float|None=None,scene_media:dict[str,list[int]]|None=None)->list[dict]:
    if media_count<1:
        raise ValueError("visual_beats_require_media")
    target=max(3.5,min(7.0,beat_seconds or float(os.getenv("LONGFORM_VISUAL_BEAT_SECONDS","5.0"))))
    beats=[];global_index=0;last_media=-1
    motions=("push-in","pan-left","pull-out","pan-right","parallax")
    all_media=list(range(media_count))
    for scene_index,scene in enumerate(scenes):
        start=float(scene.get("start") or 0)
        duration=max(1.0,float(scene.get("duration") or target))
        count=max(1,math.ceil(duration/target))
        each=duration/count
        candidates=list(dict.fromkeys((scene_media or {}).get(str(scene_index),[]) or all_media))
        if not candidates:
            candidates=all_media
        for part in range(count):
            choice=candidates[(part+scene_index)%len(candidates)]
            if choice==last_media and len(candidates)>1:
                choice=candidates[(part+scene_index+1)%len(candidates)]
            elif choice==last_media and media_count>1:
                choice=(choice+1)%media_count
            beats.append({
                "start":round(start+part*each,3),
                "duration":round(each,3),
                "mediaIndex":choice,
                "sceneIndex":scene_index,
                "motion":motions[global_index%len(motions)],
            })
            last_media=choice;global_index+=1
    return beats

