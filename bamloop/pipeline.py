"""Prepare and publish independent BAMLOOP content."""
from __future__ import annotations
import hashlib
import os
import time
from pathlib import Path
from production.queue import PublishQueue, publishing_storage_ready
from production.github_ledger import GitHubLedger, required as ledger_required, ready as ledger_ready, LedgerError, LedgerCapacity
from viral_futbol.youtube_publisher import _validate_short
from .engine import build_video, choose_idea
from .story import create_story_video
from .youtube import upload, credentials_ready, refresh_credentials
from .learning import remember_story_scenes, learned_story_advice, measured_retention_advice
from .performance import collect as collect_performance
from viral_futbol.creative_exploration import choose_creative
from viral_futbol.experiment_store import ExperimentStore
from viral_futbol.runtime_policy import safe_exploit_percent


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
        ledger=GitHubLedger() if ledger_required() else None
        recent=queue.recent(30)
        kind=select_type(recent)
        # Meme clips require a licensed source. Keep producing original stories
        # when the clip provider is unavailable instead of failing the cycle.
        if kind == 'meme' and source_url is None and not os.getenv('PEXELS_API_KEY', '').strip():
            kind = 'ai_story'
        if kind=='meme':
            idea=choose_idea(str(time.time_ns()),{row['idea'] for row in recent[:16]})
            label=idea.title
            digest=hashlib.sha256((idea.title+'|'+(source_url or '')).encode()).hexdigest()
            if ledger and ledger.exists('bamloop',digest[:24]):
                raise LedgerError('Meme concept already recorded')
            video, metadata=build_video(idea,os.getenv('MEME_OUTPUT_DIR','storage/bamloop'),source_url)
            provider='pexels' if source_url is None else 'local'
        else:
            seed=str(time.time_ns())
            # Each premise may appear again only after the short history moves on.
            for _ in range(25):
                from .story import LocalStoryProvider
                candidate=LocalStoryProvider().create(seed).idea
                candidate_id=hashlib.sha256(candidate.encode()).hexdigest()[:24]
                if candidate not in {r['idea'] for r in recent[:12]} and not (ledger and ledger.exists('bamloop',candidate_id)): break
                seed=str(int(seed)+1)
            else:
                raise LedgerError('No unused AI story concept available')
            retention_advice=measured_retention_advice(db_path())
            experiment=choose_creative(seed,retention_advice,exploit_percent=safe_exploit_percent(db_path(),"bamloop"))
            with ExperimentStore(db_path()) as experiments:
                experiments.record(seed,"bamloop",experiment)
            preferred_motion=experiment.get("motion") if experiment.get("apply") else None
            video,metadata,story,provider,_=create_story_video(seed,os.getenv('MEME_OUTPUT_DIR','storage/bamloop'),voice_fixture=voice_fixture,preferred_motion=preferred_motion)
            label=story.idea
            digest=hashlib.sha256(label.encode()).hexdigest()
            content_id=digest[:24]
            scenes=remember_story_scenes(db_path(),content_id,story)
            advice=learned_story_advice(db_path())
            metadata["creative_experiment"]=experiment
            metadata["scene_manifest"]={"count":len(scenes),"repairable":True}
            if advice:
                metadata["learned_scene_creative"]=advice
            if retention_advice:
                metadata["measured_retention_creative"]=retention_advice
        _validate_short(video)
        content_id=digest[:24]
        queued=queue.enqueue(content_id,kind,label,digest,video,metadata,provider)
        return {'content_id':content_id,'content_type':kind,'queued':queued,'video':str(video)}


def publish_pending():
    with PublishQueue(db_path(),'bamloop') as queue:
        if not credentials_ready(): return {'uploaded':0,'ready':False,**queue.counts()}
        if not publishing_storage_ready(db_path()) or (ledger_required() and not ledger_ready()):
            return {'uploaded':0,'ready':False,'persistence_blocked':not publishing_storage_ready(db_path()),
                    'ledger_blocked':ledger_required() and not ledger_ready(),**queue.counts()}
        ledger=GitHubLedger() if ledger_required() else None
        job=queue.claim(max_attempts=max(1,int(os.getenv('MEME_YOUTUBE_MAX_ATTEMPTS','4'))))
        if job is None: return {'uploaded':0,'ready':True,**queue.counts()}
        import json
        video_id = None
        try:
            _validate_short(Path(job['video_path']))
        except (ValueError,OSError) as exc:
            queue.reject(job['content_id'],str(exc))
            return {'uploaded':0,'quality_blocked':1,**queue.counts()}
        try:
            # A bad refresh token must never consume a durable upload slot.
            # Once reserved, an interrupted upload is intentionally quarantined.
            credentials = refresh_credentials()
            if ledger:
                try:
                    if not ledger.reserve('bamloop',job['content_id']):
                        queue.reject(job['content_id'],'Already recorded in publication ledger')
                        return {'uploaded':0,'duplicate':1,**queue.counts()}
                except LedgerCapacity as exc:
                    queue.defer(job['content_id'],exc.retry_at)
                    return {'uploaded':0,'scheduled':True,**queue.counts()}
                except LedgerError:
                    queue.failed(job['content_id'],'ledger_unavailable_or_limit')
                    return {'uploaded':0,'ledger_blocked':True,**queue.counts()}
            video_id=upload(Path(job['video_path']),json.loads(job['metadata']),credentials=credentials)
            if ledger:
                try: ledger.published('bamloop',job['content_id'],video_id)
                except LedgerError:
                    # A real YouTube ID is authoritative. The reservation still
                    # blocks duplicate uploads after a restart.
                    result_error = 'ledger_record_failed'
                else: result_error = None
            else: result_error = None
            queue.published(job['content_id'],video_id)
            return {'uploaded':1,'video_id':video_id,'ledger_warning':result_error,**queue.counts()}
        except Exception as exc:
            error_type=type(exc).__name__
            status=getattr(getattr(exc,'resp',None),'status',None)
            queue.failed(job['content_id'],error_type)
            return {'uploaded':0,'upload_failed':1,'upload_error_type':error_type,
                    'upload_http_status':status if isinstance(status,int) else None,**queue.counts()}


def cycle():
    try: performance=collect_performance(db_path())
    except Exception as exc: performance={'ready':False,'collected':0,'error':type(exc).__name__}
    result={'performance':performance,'publish':publish_pending()}
    try: result['prepare']=prepare()
    except Exception as exc: result['prepare']={'error':type(exc).__name__}
    result['publish_after_prepare']=publish_pending()
    return result
