from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import httplib2
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .discovery_metadata import discovery_metadata


@dataclass(frozen=True)
class YouTubeConfig:
    enabled: bool; client_id: str; client_secret: str; refresh_token: str; privacy_status: str; category_id: str; max_attempts: int; retry_seconds: int
    @classmethod
    def from_env(cls) -> "YouTubeConfig":
        privacy=os.getenv("YOUTUBE_PRIVACY_STATUS","private").casefold()
        if privacy not in {"private","unlisted","public"}: privacy="private"
        try: max_attempts=max(1,int(os.getenv("YOUTUBE_MAX_ATTEMPTS","4")))
        except ValueError: max_attempts=4
        try: retry_seconds=max(30,int(os.getenv("YOUTUBE_RETRY_SECONDS","900")))
        except ValueError: retry_seconds=900
        return cls(os.getenv("YOUTUBE_ENABLED","false").casefold() in {"1","true","yes","on"},os.getenv("YOUTUBE_CLIENT_ID","").strip(),os.getenv("YOUTUBE_CLIENT_SECRET","").strip(),os.getenv("YOUTUBE_REFRESH_TOKEN","").strip(),privacy,os.getenv("YOUTUBE_CATEGORY_ID","17").strip() or "17",max_attempts,retry_seconds)
    @property
    def ready(self)->bool: return self.enabled and all((self.client_id,self.client_secret,self.refresh_token))


class PublicationStore:
    def __init__(self,db_path:str):
        # News scanning can stop before Store opens; initialize jobs independently.
        from .service import Store
        with Store(db_path):
            pass
        Path(db_path).parent.mkdir(parents=True,exist_ok=True); self.db=sqlite3.connect(db_path,timeout=30); self.db.row_factory=sqlite3.Row; self.db.execute("PRAGMA busy_timeout = 30000")
        self.db.execute("CREATE TABLE IF NOT EXISTS youtube_manifests (story_id TEXT PRIMARY KEY,title TEXT NOT NULL,language TEXT NOT NULL,sources_json TEXT NOT NULL,created_at REAL NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS youtube_publications (story_id TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,video_id TEXT,last_error TEXT,updated_at REAL NOT NULL,next_retry_at REAL NOT NULL DEFAULT 0)"); self.db.commit()
    def __enter__(self): return self
    def __exit__(self,*_args)->None: self.db.close()
    def remember(self,story_id:str,title:str,language:str,sources:list[str])->None:
        with self.db: self.db.execute("INSERT OR IGNORE INTO youtube_manifests (story_id,title,language,sources_json,created_at) VALUES (?,?,?,?,?)",(story_id,title[:180],language,json.dumps(sources,ensure_ascii=False),time.time()))
    def ready_jobs(self,limit:int=2)->list[dict]:
        rows=self.db.execute("SELECT j.story_id,j.output_url,j.language,COALESCE(m.title,'Futbol gündeminde son dakika') AS title,COALESCE(m.sources_json,'[]') AS sources_json FROM jobs j LEFT JOIN youtube_manifests m ON m.story_id=j.story_id LEFT JOIN youtube_publications p ON p.story_id=j.story_id WHERE j.status='complete' AND j.output_url IS NOT NULL AND (p.story_id IS NULL OR (p.status='failed' AND p.attempts<? AND p.next_retry_at<=?)) ORDER BY j.updated_at ASC LIMIT ?",(YouTubeConfig.from_env().max_attempts,time.time(),max(1,limit))).fetchall(); return [dict(row) for row in rows]
    def claim(self,story_id:str)->bool:
        now=time.time()
        with self.db:
            self.db.execute("BEGIN IMMEDIATE"); row=self.db.execute("SELECT status,next_retry_at FROM youtube_publications WHERE story_id=?",(story_id,)).fetchone()
            if row and (row["status"] in {"uploading","published"} or float(row["next_retry_at"])>now): return False
            self.db.execute("INSERT INTO youtube_publications(story_id,status,attempts,updated_at) VALUES (?,'uploading',1,?) ON CONFLICT(story_id) DO UPDATE SET status='uploading',attempts=attempts+1,last_error=NULL,updated_at=?,next_retry_at=0",(story_id,now,now)); return True
    def published(self,story_id:str,video_id:str)->None:
        with self.db: self.db.execute("UPDATE youtube_publications SET status='published',video_id=?,last_error=NULL,updated_at=?,next_retry_at=0 WHERE story_id=?",(video_id,time.time(),story_id))
    def failed(self,story_id:str,error:str,retry_seconds:int)->None:
        now=time.time()
        with self.db:
            self.db.execute("UPDATE youtube_publications SET status='failed',last_error=?,updated_at=?,next_retry_at=? WHERE story_id=?",(error[:2000],now,now+retry_seconds,story_id))

    def rejected(self,story_id:str,error:str)->None:
        now=time.time()
        with self.db:
            self.db.execute("UPDATE youtube_publications SET status='rejected',last_error=?,updated_at=?,next_retry_at=0 WHERE story_id=?",(error[:2000],now,story_id))

    def counts(self)->dict[str,int]: return {str(row["status"]):int(row["count"]) for row in self.db.execute("SELECT status,COUNT(*) AS count FROM youtube_publications GROUP BY status").fetchall()}


def remember_manifest(db_path:str,story_id:str,title:str,language:str,sources:list[str])->None:
    with PublicationStore(db_path) as store: store.remember(story_id,title,language,sources)


def _download(url:str,destination:Path,api_key:str,timeout:int)->None:
    if url.startswith("file://"): shutil.copyfile(Path(urllib.request.url2pathname(urllib.parse.urlsplit(url).path)),destination)
    else:
        headers={"User-Agent":"ViralFutbol/1.0"}
        if api_key: headers["x-api-key"]=api_key
        request=urllib.request.Request(url,headers=headers)
        with urllib.request.urlopen(request,timeout=max(30,timeout)) as response,destination.open("wb") as output:
            while chunk:=response.read(1024*1024): output.write(chunk)
    if destination.stat().st_size<1024 or b"ftyp" not in destination.read_bytes()[:64]: raise ValueError("Video output is not a valid MP4")


def _probe(path:Path)->dict:
    command=["ffprobe","-v","error","-show_entries","format=duration:stream=index,codec_type,codec_name,width,height","-of","json",str(path)]
    try: completed=subprocess.run(command,capture_output=True,text=True,check=True,timeout=30)
    except (subprocess.CalledProcessError,subprocess.TimeoutExpired,FileNotFoundError) as exc: raise ValueError(f"MP4 quality probe failed: {exc}") from exc
    try: return json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc: raise ValueError("MP4 quality probe returned invalid metadata") from exc


def _validate_short(path:Path)->dict:
    probe=_probe(path); streams=probe.get("streams") or []; videos=[s for s in streams if s.get("codec_type")=="video"]; audios=[s for s in streams if s.get("codec_type")=="audio"]
    if not videos: raise ValueError("Quality gate: video stream missing")
    if not audios: raise ValueError("Quality gate: audio stream missing")
    video=videos[0]; width=int(video.get("width") or 0); height=int(video.get("height") or 0)
    try: duration=float((probe.get("format") or {}).get("duration") or 0)
    except (TypeError,ValueError): duration=0
    try: min_seconds=max(5,float(os.getenv("SHORTS_MIN_DURATION_SECONDS","12")))
    except ValueError: min_seconds=12.0
    try: max_seconds=min(180,float(os.getenv("SHORTS_MAX_DURATION_SECONDS","70")))
    except ValueError: max_seconds=70.0
    if duration<min_seconds or duration>max_seconds: raise ValueError(f"Quality gate: duration {duration:.1f}s outside {min_seconds:.0f}-{max_seconds:.0f}s")
    # The production FFmpeg renderer intentionally outputs 720p on the 512 MB
    # Render instance. Do not reject its own valid vertical Shorts by default.
    if width<int(os.getenv("SHORTS_MIN_WIDTH","720")) or height<int(os.getenv("SHORTS_MIN_HEIGHT","1280")): raise ValueError(f"Quality gate: resolution too low ({width}x{height})")
    if video.get('codec_name') != 'h264' or audios[0].get('codec_name') != 'aac': raise ValueError('Quality gate: H.264/AAC required')
    if height<=width or abs(width / height - 9 / 16) > 0.02:
        raise ValueError(f"Quality gate: video is not 9:16 ({width}x{height})")
    if path.stat().st_size<100_000: raise ValueError(f"Quality gate: file too small ({path.stat().st_size} bytes)")
    return {"duration":round(duration,2),"width":width,"height":height,"video_codec":video.get("codec_name"),"audio_codec":audios[0].get("codec_name"),"bytes":path.stat().st_size}


def _metadata(job:dict)->tuple[str,str,list[str]]:
    language=str(job.get("language") or "tr")
    raw_title=str(job.get("title") or "Futbol gündeminde son dakika").strip()
    metadata=discovery_metadata(raw_title, language)
    return str(metadata["title"]), str(metadata["description"]), list(metadata["tags"])


def _upload(path:Path,job:dict,config:YouTubeConfig)->str:
    from google.oauth2.credentials import Credentials
    from google_auth_httplib2 import AuthorizedHttp
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    credentials=Credentials(token=None,refresh_token=config.refresh_token,token_uri="https://oauth2.googleapis.com/token",client_id=config.client_id,client_secret=config.client_secret,scopes=["https://www.googleapis.com/auth/youtube.upload"])
    youtube=build("youtube","v3",http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=60)),cache_discovery=False)
    title,description,tags=_metadata(job)
    request=youtube.videos().insert(part="snippet,status",body={"snippet":{"title":title,"description":description,"tags":tags,"categoryId":config.category_id,"defaultLanguage":str(job.get("language") or "tr")},"status":{"privacyStatus":config.privacy_status,"selfDeclaredMadeForKids":False}},media_body=MediaFileUpload(str(path),mimetype="video/mp4",chunksize=8*1024*1024,resumable=True)); response=None
    deadline=time.monotonic()+300
    for _ in range(120):
        if response is not None: break
        if time.monotonic()>deadline: raise TimeoutError("YouTube upload deadline exceeded")
        _,response=request.next_chunk()
    if response is None: raise TimeoutError("YouTube upload exceeded chunk limit")
    video_id=str((response or {}).get("id") or "")
    if not video_id: raise RuntimeError("YouTube accepted upload without a video id")
    return video_id


def publish_ready(settings,limit:int=2)->dict:
    """Queue completed renders and publish only in this channel's valid slot."""
    from production.queue import PublishQueue, publishing_storage_ready
    from production.github_ledger import GitHubLedger, required as ledger_required, ready as ledger_ready, LedgerError, LedgerCapacity
    config=YouTubeConfig.from_env()
    result={"enabled":config.enabled,"ready":config.ready,"published":0,"failed":0,"quality_blocked":0,"skipped":0,"skip_reasons":{},"validated":[]}
    with PublicationStore(settings.db_path) as manifests, PublishQueue(settings.db_path,'viral_futbol') as queue:
        # Discovery and rendering continue even while YouTube is unavailable.
        for job in manifests.ready_jobs(limit=100):
            story_id=str(job['story_id'])
            queue.enqueue(story_id,'football',str(job['title']),story_id,str(job['output_url']),job)
        result.update(queue.counts())
        result['next_publish_slot']=queue.next_slot()
        if not config.ready: return result
        if not publishing_storage_ready(str(settings.db_path)) or (ledger_required() and not ledger_ready()):
            result['ready']=False
            result['persistence_blocked']=not publishing_storage_ready(str(settings.db_path))
            result['ledger_blocked']=ledger_required() and not ledger_ready()
            return result
        ledger = GitHubLedger() if ledger_required() else None
        for _ in range(max(0,limit)):
            job=queue.claim(max_attempts=config.max_attempts)
            if job is None: break
            story_id=str(job['content_id'])
            try:
                with tempfile.TemporaryDirectory(prefix='viral-futbol-') as directory:
                    video_path=Path(directory)/f'{story_id}.mp4'
                    _download(str(job['video_path']),video_path,settings.mpt_api_key,settings.mpt_request_timeout)
                    try: quality=_validate_short(video_path)
                    except ValueError as exc:
                        result['quality_blocked']+=1; queue.reject(story_id,exc); continue
                    result['validated'].append({'story_id':story_id,**quality})
                    if ledger:
                        try:
                            if not ledger.reserve('viral_futbol',story_id):
                                queue.reject(story_id,'Already recorded in publication ledger')
                                result['skipped']+=1
                                result['skip_reasons']['ledger_record_exists'] = result['skip_reasons'].get('ledger_record_exists', 0) + 1
                                continue
                        except LedgerCapacity as exc:
                            queue.defer(story_id,exc.retry_at)
                            result['skipped']+=1
                            result['skip_reasons']['ledger_capacity'] = result['skip_reasons'].get('ledger_capacity', 0) + 1
                            continue
                        except LedgerError:
                            queue.failed(story_id,'ledger_unavailable_or_limit')
                            result['skipped']+=1
                            result['skip_reasons']['ledger_unavailable'] = result['skip_reasons'].get('ledger_unavailable', 0) + 1
                            continue
                    video_id=_upload(video_path,json.loads(job['metadata']),config)
                if ledger:
                    ledger.published('viral_futbol',story_id,video_id)
                queue.published(story_id,video_id)
                result['published']+=1
                try:
                    manifests.claim(story_id)
                    manifests.published(story_id,video_id)
                except Exception:
                    print(f'ViralFutbol performance indexing deferred ({story_id})',flush=True)
            except Exception as exc:
                queue.failed(story_id,type(exc).__name__)
                result['failed']+=1
                # Avoid printing HTTP error bodies that might include credentials.
                print(f'ViralFutbol YouTube upload failed ({story_id}): {type(exc).__name__}',flush=True)
        result.update(queue.counts())
        result['next_publish_slot']=queue.next_slot()
        result['status_counts']=manifests.counts()
    return result
