"""Timed TTS for documentary narration using Edge word boundaries with offline fallback."""
from __future__ import annotations
import asyncio,os,re,subprocess
from pathlib import Path

async def _edge_stream(text:str,voice:str,path:Path)->list[dict]:
    import edge_tts
    rate=os.getenv("LONGFORM_TTS_RATE","+5%")
    pitch=os.getenv("LONGFORM_TTS_PITCH","+0Hz")
    communicate=edge_tts.Communicate(text=text,voice=voice,rate=rate,pitch=pitch,volume="+8%")
    tokens=[]
    with path.open("wb") as audio:
        async for chunk in communicate.stream():
            kind=chunk.get("type")
            if kind=="audio":
                audio.write(chunk.get("data") or b"")
            elif kind=="WordBoundary":
                start=float(chunk.get("offset") or 0)/10000.0
                duration=max(1.0,float(chunk.get("duration") or 0)/10000.0)
                value=str(chunk.get("text") or "").strip()
                if value:
                    tokens.append({"text":value,"startMs":round(start,2),"endMs":round(start+duration,2)})
    return tokens

def _duration_ms(path:Path)->float:
    completed=subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)],
        capture_output=True,text=True,timeout=30,check=True,
    )
    return max(1.0,float((completed.stdout or "0").strip() or 0)*1000.0)

def _approximate(text:str,duration_ms:float)->list[dict]:
    words=re.findall(r"\S+",text)
    if not words:
        return []
    weights=[max(1,len(re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]+","",word))) for word in words]
    total=max(1,sum(weights));cursor=0.0;tokens=[]
    for word,weight in zip(words,weights):
        span=duration_ms*weight/total
        tokens.append({"text":word,"startMs":round(cursor,2),"endMs":round(cursor+span,2)})
        cursor+=span
    return tokens

def _pages(tokens:list[dict],max_words:int=7,max_span_ms:float=2600.0)->list[dict]:
    pages=[];current=[]
    def flush():
        nonlocal current
        if not current:
            return
        pages.append({
            "text":" ".join(str(x["text"]) for x in current).strip(),
            "startMs":float(current[0]["startMs"]),
            "endMs":float(current[-1]["endMs"]),
            "tokens":[dict(x) for x in current],
        })
        current=[]
    for token in tokens:
        if current and (len(current)>=max_words or float(token["endMs"])-float(current[0]["startMs"])>max_span_ms):
            flush()
        current.append(token)
        if str(token["text"]).rstrip().endswith((".","!","?",";",":")) and len(current)>=3:
            flush()
    flush()
    return pages

def synthesize_timed(text:str,path:Path,voice:str="tr-TR-EmelNeural")->dict:
    path.parent.mkdir(parents=True,exist_ok=True)
    provider="edge";tokens=[]
    try:
        tokens=asyncio.run(asyncio.wait_for(
            _edge_stream(text,voice,path),
            timeout=max(60,int(os.getenv("LONGFORM_TTS_TIMEOUT_SECONDS","180"))),
        ))
    except Exception as exc:
        print(f"Timed Edge TTS unavailable, using offline voice: {type(exc).__name__}",flush=True)
        path.unlink(missing_ok=True)
        subprocess.run(["espeak-ng","-v","tr","-s","155","-w",str(path),text],check=True,timeout=240)
        provider="espeak"
    if not path.exists() or path.stat().st_size<1024:
        raise RuntimeError("longform_tts_failed")
    if not tokens:
        tokens=_approximate(text,_duration_ms(path))
    captions=_pages(tokens)
    return {"audio":path,"tokens":tokens,"captions":captions,"provider":provider}
