"""End-to-end autonomous long-form production for ViralFutbol and BAMLOOP."""
from __future__ import annotations
import json,os,time
from pathlib import Path
from production.format_scheduler import channel_kind
from production.timed_tts import synthesize_timed
from production.documentary_media import build_documentary_media, visual_beats
from production.longform_narration import generate_narration
from production.longform_producer import prepare_contract,attach_assets
from production.longform_renderer import render_contract
from production.longform_sources import research
from production.music import instrumental
from production.queue import PublishQueue

PLAYERS=("Osimhen","Icardi","Salah","Mbappe","Haaland","Lamine Yamal","Arda Güler","Hakan Çalhanoğlu","Kerem Aktürkoğlu","Cristiano Ronaldo","Lionel Messi","Kevin De Bruyne")
CLUBS=("Galatasaray","Fenerbahçe","Beşiktaş","Trabzonspor","Real Madrid","Barcelona","Liverpool","Manchester City","Bayern Munich","Inter","Milan","Juventus")
EXPLAINERS=("Yapay zekâ","Kara delik","GPS","Lityum iyon pil","3D yazıcı","Kuantum bilgisayar","İnternet","Uydu navigasyonu","Güneş paneli","Elektrikli otomobil","Robotik","Sanal gerçeklik")

def _metadata_format(row:dict)->str:
    try:
        return str(json.loads(row.get("metadata") or "{}").get("content_format") or "short")
    except (TypeError,ValueError,json.JSONDecodeError):
        return "video" if row.get("content_type")=="video" else "short"

def recent_longforms(db_path:str,channel:str,limit:int=100)->list[dict]:
    with PublishQueue(db_path,channel) as queue:
        return [row for row in queue.recent(limit) if _metadata_format(row)=="video"]

def last_activity(db_path:str,channel:str)->float|None:
    rows=recent_longforms(db_path,channel,100)
    if not rows:
        return None
    return max(float(row.get("published_at") or row.get("rendered_at") or row.get("created_at") or 0) for row in rows)

def choose_subject(channel:str,kind:str,recent:list[dict])->str:
    cooldown=max(1,int(os.getenv("LONGFORM_TOPIC_COOLDOWN_DAYS","45")))*86400
    cutoff=time.time()-cooldown
    used={str(row.get("idea") or "").casefold() for row in recent if float(row.get("created_at") or 0)>=cutoff}
    if channel=="viral_futbol":
        pool=PLAYERS if kind=="player_career" else CLUBS if kind=="club_history" else PLAYERS+CLUBS
    elif channel=="bamloop":
        pool=EXPLAINERS
    else:
        raise ValueError("unsupported channel")
    offset=(int(time.time()//86400)+len(recent))%len(pool)
    for step in range(len(pool)):
        candidate=pool[(offset+step)%len(pool)]
        if candidate.casefold() not in used:
            return candidate
    raise ValueError("no_unused_longform_topic")

def _description(base:str,evidence:list,credits:list[dict])->str:
    source_lines=[];seen=set()
    for item in evidence:
        key=(item.source,item.url)
        if key in seen: continue
        seen.add(key)
        source_lines.append(f"- {item.source}: {item.url}" if item.url else f"- {item.source}")
        if len(source_lines)>=8: break
    credit_lines=[];seen_credit=set()
    for item in credits:
        page=str(item.get("page") or "")
        key=page or str(item.get("title") or "")
        if not key or key in seen_credit: continue
        seen_credit.add(key)
        artist=str(item.get("artist") or "Wikimedia contributor")
        license_name=str(item.get("license") or "Wikimedia Commons")
        credit_lines.append(f"- {artist} — {license_name}" + (f" — {page}" if page else ""))
        if len(credit_lines)>=8: break
    parts=[base.strip()]
    if source_lines:
        parts.append("Kaynaklar:\n"+"\n".join(source_lines))
    if credit_lines:
        parts.append("Görsel kredileri:\n"+"\n".join(credit_lines))
    return "\n\n".join(parts)[:4800]

def produce_once(*,channel:str,db_path:str,output_dir:str,voice:str="tr-TR-EmelNeural",force_remotion:bool=False)->dict:
    directory=Path(output_dir);directory.mkdir(parents=True,exist_ok=True)
    now=time.time()
    if os.getenv("LONGFORM_RENDER_ONLY_WHEN_SLOT_READY","true").casefold() in {"1","true","yes","on"}:
        with PublishQueue(db_path,channel) as slot_queue:
            next_slot=slot_queue.next_slot(now=now,content_format="video")
        if next_slot>now+60:
            return {"queued":False,"deferred":True,"reason":"video_publish_slot_not_ready","next_video_slot":next_slot}
    recent=recent_longforms(db_path,channel,100)
    sequence=len(recent)
    kind=channel_kind(channel,sequence)
    subject=choose_subject(channel,kind,recent)
    evidence=research(subject,min_items=max(8,int(os.getenv("LONGFORM_MIN_EVIDENCE","10"))),max_items=24)
    contract=prepare_contract(subject=subject,channel=channel,evidence=evidence,kind=kind,target_seconds=210,
                              min_claims=max(8,int(os.getenv("LONGFORM_MIN_EVIDENCE","10"))))
    narration=generate_narration(subject,contract["script"])
    audio=directory/f"{contract['content_id']}-voice.mp3"
    frames=[];credits=[];music=None
    try:
        tts=synthesize_timed(narration["text"],audio,voice)
        documentary=build_documentary_media(subject=subject,scenes=contract["editorial"]["scenes"],
                                            claims=contract["script"]["verified_claims"],output_dir=directory,
                                            content_id=contract["content_id"],channel=channel,target_assets=12)
        frames=documentary["media"];credits=documentary["credits"]
        beats=visual_beats(contract["editorial"]["scenes"],len(frames),scene_media=documentary.get("scene_media"))

        if os.getenv("LONGFORM_MUSIC_ENABLED","true").casefold() in {"1","true","yes","on"}:
            music=instrumental(directory/f"{contract['content_id']}-bed.wav")
        ready=attach_assets(contract,media=frames,audio=audio,music=music)
        ready["visual_beats"]=beats
        ready["media_report"]=documentary["report"]
        ready["captions"]=tts["captions"]
        output=directory/f"{contract['content_id']}.mp4"
        rendered=render_contract(ready,output,force=force_remotion)
        metadata=dict(contract["metadata"])
        metadata["word_count"]=narration["word_count"]
        metadata["script_provider"]=narration["provider"]
        metadata["renderer"]=rendered["renderer"]
        metadata["tts_provider"]=tts["provider"]
        metadata["caption_pages"]=len(tts["captions"])
        metadata["post_qc"]=rendered.get("post_qc") or {}
        metadata["visual_beat_count"]=len(beats)
        metadata["documentary_media"]=documentary["report"]
        metadata["description"]=_description(str(metadata.get("description") or ""),evidence,credits)
        metadata["source_count"]=len({item.source.casefold() for item in evidence})
        video_path=output.resolve().as_uri() if channel=="viral_futbol" else str(output.resolve())
        with PublishQueue(db_path,channel) as queue:
            queued=queue.enqueue(contract["content_id"],"video",subject,contract["content_hash"],video_path,metadata,
                                 provider="wikidata+commons+pexels")
        return {"queued":queued,"content_id":contract["content_id"],"subject":subject,"kind":kind,
                "video":str(output),"word_count":narration["word_count"],"script_provider":narration["provider"],
                "renderer":rendered["renderer"],"quality":rendered["quality"],"post_qc":rendered.get("post_qc") or {},
                "visual_beat_count":len(beats),"caption_pages":len(tts["captions"]),"documentary_media":documentary["report"]}
    finally:
        for frame in frames:
            Path(frame).unlink(missing_ok=True)
        audio.unlink(missing_ok=True)
        if music:
            Path(music).unlink(missing_ok=True)
