"""Prepare and publish independent BAMLOOP content."""
from __future__ import annotations
import hashlib
import os
import time
from pathlib import Path
from production.queue import PublishQueue, publishing_storage_ready
from production.github_ledger import GitHubLedger, required as ledger_required, ready as ledger_ready, LedgerError, LedgerCapacity
from viral_futbol.youtube_publisher import _validate_short, _validate_video
from .engine import build_video, choose_idea
from .story import create_story_video
from .youtube import upload, credentials_ready, refresh_credentials
from .learning import remember_story_scenes, learned_story_advice, measured_retention_advice
from .performance import collect as collect_performance
from viral_futbol.creative_exploration import choose_creative
from viral_futbol.experiment_store import ExperimentStore
from viral_futbol.runtime_policy import safe_exploit_percent
from production.format_scheduler import decide as decide_formats
from production.longform_runtime import last_activity as last_longform_activity, produce_once as produce_longform


def db_path():
    from production.publishing_policy import unified_channel
    if unified_channel():
        from viral_futbol.config import Settings
        return os.getenv('NEWS_DB_PATH') or Settings().db_path
    return os.getenv('MEME_DB_PATH') or str(Path(os.getenv('MEME_OUTPUT_DIR','storage/bamloop'))/'bamloop.sqlite3')


def select_type(recent):
    from .meme_catalog import reaction_mode
    if reaction_mode():
        return 'meme'
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
        from .meme_catalog import reaction_mode, catalog, content_id as reviewed_id
        from .content_mix import mixed_mode, next_category
        if mixed_mode():
            from .original_meme import story_bank, identity, build_original_video
            from .reaction_meme import build_reaction_video
            category, sequence = next_category(queue)
            # Global slots alternate original skits and reviewed clips. Football
            # slots never silently become unrelated stock footage.
            reviewed = []
            if category == 'global' and sequence % 2 == 0:
                reviewed = [(reviewed_id(clip), clip) for clip in catalog()]
            originals = [(identity(story), story) for story in story_bank(category)]
            for content_id, candidate in reviewed + originals:
                if queue.db.execute('SELECT 1 FROM publish_queue WHERE channel=? AND content_id=?',
                                    ('bamloop', content_id)).fetchone():
                    continue
                if ledger and ledger.exists('bamloop', content_id):
                    continue
                output_dir = os.getenv('MEME_OUTPUT_DIR','storage/bamloop')
                if 'sha256' in candidate:
                    video, metadata = build_reaction_video(candidate, output_dir)
                    digest, provider = candidate['sha256'], 'reviewed_clip'
                else:
                    video, metadata = build_original_video(candidate, output_dir)
                    digest, provider = hashlib.sha256(candidate['id'].encode()).hexdigest(), 'original_animation'
                metadata['meme_category'] = category
                metadata['growth_lane'] = 'football_meme' if category == 'football' else 'global_meme'
                _validate_short(video)
                queued = queue.enqueue(content_id, 'meme', metadata['title'], digest, video, metadata, provider)
                return {'content_id':content_id, 'content_type':'meme', 'queued':queued,
                        'video':str(video), 'meme_category':category, 'provider':provider}
            return {'deferred':True, 'reason':'meme_category_catalog_exhausted',
                    'meme_category':category, 'original_stories':len(originals)}
        if reaction_mode():
            from .reaction_meme import build_reaction_video
            # A new caption must not recycle the same source clip after restart.
            for clip in catalog():
                content_id = reviewed_id(clip)
                if any(row['content_id'] == content_id for row in recent):
                    continue
                if ledger and ledger.exists('bamloop', content_id):
                    continue
                video, metadata = build_reaction_video(clip, os.getenv('MEME_OUTPUT_DIR','storage/bamloop'))
                queued = queue.enqueue(content_id, 'meme', clip['title'], clip['sha256'], video, metadata, 'reviewed_clip')
                return {'content_id':content_id, 'content_type':'meme', 'queued':queued,
                        'video':str(video), 'meme_contract':metadata['meme_contract'], 'clip_id':clip['id']}
            return {'deferred':True, 'reason':'reviewed_meme_catalog_exhausted', 'reviewed_clips':len(catalog())}
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
        from .meme_catalog import quarantine_legacy, require_reviewed_meme
        quarantine_legacy(queue)
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
            job_metadata=json.loads(job['metadata'])
            require_reviewed_meme(job_metadata)
            _validate_video(Path(job['video_path']),str(job_metadata.get('content_format') or 'short'))
        except (ValueError,OSError) as exc:
            queue.reject(job['content_id'],str(exc))
            return {'uploaded':0,'quality_blocked':1,**queue.counts()}
        try:
            # A bad refresh token must never consume a durable upload slot.
            # Once reserved, an interrupted upload is intentionally quarantined.
            credentials = refresh_credentials()
            from bamloop.youtube import verify_channel
            channel = verify_channel(credentials)
            from production.youtube_auth import record_auth
            record_auth('bamloop',channel=channel)
            if ledger:
                try:
                    ledger.audit_capacity('bamloop', credentials, channel['id'])
                    if not ledger.reserve('bamloop',job['content_id'], content_format=str(job_metadata.get('content_format') or 'short')):
                        queue.reject(job['content_id'],'Already recorded in publication ledger')
                        return {'uploaded':0,'duplicate':1,**queue.counts()}
                except LedgerCapacity as exc:
                    queue.defer(job['content_id'],exc.retry_at)
                    return {'uploaded':0,'scheduled':True,**queue.counts()}
                except LedgerError:
                    queue.failed(job['content_id'],'ledger_unavailable_or_limit')
                    return {'uploaded':0,'ledger_blocked':True,**queue.counts()}
            video_id=upload(Path(job['video_path']),job_metadata,credentials=credentials)
            if ledger:
                try: ledger.published('bamloop',job['content_id'],video_id)
                except LedgerError:
                    # A real YouTube ID is authoritative. The reservation still
                    # blocks duplicate uploads after a restart.
                    result_error = 'ledger_record_failed'
                else: result_error = None
            else: result_error = None
            queue.published(job['content_id'],video_id)
            try:
                from production.youtube_auth import verify_public_upload
                from production.publishing_policy import bamloop_env
                public_verified=verify_public_upload(credentials,video_id) if bamloop_env('PRIVACY_STATUS','private').casefold()=='public' else False
            except Exception:
                public_verified=False
            return {'uploaded':1,'video_id':video_id,'public_verified':public_verified,
                    'verification_warning':None if public_verified else 'youtube_public_unconfirmed',
                    'ledger_warning':result_error,**queue.counts()}
        except Exception as exc:
            from production.youtube_auth import safe_oauth_error
            error_type=safe_oauth_error(exc) if type(exc).__name__ in {'RefreshError','ChannelMismatch','ChannelNotConfigured'} else type(exc).__name__
            if type(exc).__name__ in {'RefreshError','ChannelMismatch','ChannelNotConfigured'}:
                from production.youtube_auth import record_auth
                record_auth('bamloop',error=error_type)
            status=getattr(getattr(exc,'resp',None),'status',None)
            queue.failed(job['content_id'],error_type)
            return {'uploaded':0,'upload_failed':1,'upload_error_type':error_type,
                    'upload_http_status':status if isinstance(status,int) else None,**queue.counts()}


def cycle():
    path=db_path()
    try: performance=collect_performance(path)
    except Exception as exc: performance={'ready':False,'collected':0,'error':type(exc).__name__}
    result={'performance':performance,'publish':publish_pending()}
    enabled=os.getenv('BAMLOOP_LONGFORM_ENABLED',os.getenv('LONGFORM_ENABLED','false')).casefold() in {'1','true','yes','on'}
    try: interval=float(os.getenv('BAMLOOP_LONGFORM_INTERVAL_HOURS',os.getenv('LONGFORM_INTERVAL_HOURS','24')))
    except ValueError: interval=24.0
    decision=decide_formats(last_longform_at=last_longform_activity(path,'bamloop'),longform_enabled=enabled,interval_hours=interval)
    result['formats']={'shorts':decision.shorts,'longform':decision.longform,'reason':decision.reason}
    if decision.longform:
        if not credentials_ready():
            result['longform']={'deferred':True,'reason':'youtube_credentials_not_ready'}
        else:
            try:
                credentials=refresh_credentials()
                from bamloop.youtube import verify_channel
                verify_channel(credentials)
                result['longform']=produce_longform(
                    channel='bamloop',db_path=path,
                    output_dir=os.getenv('BAMLOOP_LONGFORM_OUTPUT_DIR',str(Path(os.getenv('MEME_OUTPUT_DIR','storage/bamloop'))/'longform')),
                    voice=os.getenv('BAMLOOP_LONGFORM_VOICE','tr-TR-EmelNeural'))
            except Exception as exc:
                result['longform']={'deferred':True,'error':type(exc).__name__,'reason':'longform_preflight_or_production_failed'}
    else:
        result['longform']={'deferred':True,'reason':decision.reason}
    try: result['prepare']=prepare()
    except Exception as exc: result['prepare']={'error':type(exc).__name__}
    result['publish_after_prepare']=publish_pending()
    return result
