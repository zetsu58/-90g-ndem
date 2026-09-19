"""Prepare and publish independent BAMLOOP content."""
from __future__ import annotations
import hashlib
import os
import time
from pathlib import Path
from production.queue import PublishQueue, persistent_render_path
from viral_futbol.youtube_publisher import _validate_short
from .engine import build_video, choose_idea
from .story import create_story_video
from .youtube import upload, credentials_ready


def db_path():
    return os.getenv('MEME_DB_PATH') or str(Path(os.getenv('MEME_OUTPUT_DIR','storage/bamloop'))/'bamloop.sqlite3')


def select_type(recent):
    meme=max(0,int(os.getenv('BAMLOOP_MEME_WEIGHT','1')))
    story=max(0,int(os.getenv('BAMLOOP_AI_STORY_WEIGHT','1')))
    if not meme + story: raise ValueError('At least one content weight must be positive')
    kinds=['meme']*meme+['ai_story']*story
    last=[row['content_type'] for row in recent[:4]]
    if len(last)>=3 and len(set(last[:3]))==1 and any(k!=last[0] for k in kinds):
        return next(k for k in kinds if k!=last[0])
    counts={kind:last.count(kind) for kind in set(kinds)}
    return min(set(kinds),key=lambda kind: (counts[kind]+1)/kinds.count(kind))


def prepare(*, source_url=None, voice_fixture=None):
    with PublishQueue(db_path(),'bamloop') as queue:
        recent=queue.recent(30)
        kind=select_type(recent)
        if kind=='meme':
            idea=choose_idea(str(time.time_ns()),{row['idea'] for row in recent[:16]})
            video, metadata=build_video(idea,os.getenv('MEME_OUTPUT_DIR','storage/bamloop'),source_url)
            label=idea.title
            digest=hashlib.sha256((idea.title+'|'+(source_url or '')).encode()).hexdigest()
            provider='pexels' if source_url is None else 'local'
        else:
            seed=str(time.time_ns())
            # Each premise may appear again only after the short history moves on.
            for _ in range(25):
                from .story import LocalStoryProvider
                if LocalStoryProvider().create(seed).idea not in {r['idea'] for r in recent[:12]}: break
                seed=str(int(seed)+1)
            video,metadata,story,provider,_=create_story_video(seed,os.getenv('MEME_OUTPUT_DIR','storage/bamloop'),voice_fixture=voice_fixture)
            label=story.idea
            digest=hashlib.sha256(label.encode()).hexdigest()
        _validate_short(video)
        content_id=digest[:24]
        queued=queue.enqueue(content_id,kind,label,digest,video,metadata,provider)
        return {'content_id':content_id,'content_type':kind,'queued':queued,'video':str(video)}


def publish_pending():
    with PublishQueue(db_path(),'bamloop') as queue:
        if not credentials_ready(): return {'uploaded':0,'ready':False,**queue.counts()}
        if not persistent_render_path(db_path()):
            return {'uploaded':0,'ready':False,'persistence_blocked':True,**queue.counts()}
        job=queue.claim(max_attempts=max(1,int(os.getenv('MEME_YOUTUBE_MAX_ATTEMPTS','4'))))
        if job is None: return {'uploaded':0,'ready':True,**queue.counts()}
        import json
        try:
            _validate_short(Path(job['video_path']))
        except (ValueError,OSError) as exc:
            queue.reject(job['content_id'],str(exc))
            return {'uploaded':0,'quality_blocked':1,**queue.counts()}
        try:
            video_id=upload(Path(job['video_path']),json.loads(job['metadata']))
            queue.published(job['content_id'],video_id)
            return {'uploaded':1,'video_id':video_id,**queue.counts()}
        except Exception as exc:
            queue.failed(job['content_id'],type(exc).__name__)
            return {'uploaded':0,'upload_failed':1,**queue.counts()}


def cycle():
    result={'publish':publish_pending()}
    try: result['prepare']=prepare()
    except Exception as exc: result['prepare']={'error':type(exc).__name__}
    result['publish_after_prepare']=publish_pending()
    return result
