import json
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

import pytest
from bamloop.content_mix import next_category, pattern
from bamloop.original_meme import story_bank, identity, validate_metadata, frame, CONTRACT
from bamloop.meme_catalog import require_reviewed_meme
from production.queue import PublishQueue
from production.growth_report import record_snapshot, report
from viral_futbol.performance_learning import PerformanceSample


def test_rotation_survives_restarts_and_ignores_old_unclassified_jobs(tmp_path,monkeypatch):
    monkeypatch.delenv('BAMLOOP_CATEGORY_PATTERN',raising=False)
    path=str(tmp_path/'queue.db')
    with PublishQueue(path,'bamloop') as queue:
        queue.enqueue('old','meme','old','old','old.mp4',{})
    actual=[]
    for index in range(10):
        with PublishQueue(path,'bamloop') as queue:
            category,_=next_category(queue)
            actual.append(category)
            queue.enqueue(str(index),'meme','new',str(index),'new.mp4',{'meme_category':category})
    assert actual==['global','football','global','football','global']*2


def test_both_categories_required(monkeypatch):
    monkeypatch.setenv('BAMLOOP_CATEGORY_PATTERN','football,football')
    with pytest.raises(ValueError,match='both_football_and_global'): pattern()


def test_original_contract_rejects_changed_story_and_old_mode(monkeypatch):
    story=story_bank('football')[0]
    metadata={'meme_contract':CONTRACT,'meme_category':'football','story_id':story['id'],
              'original_story':story,'content_id':identity(story),'content_format':'short'}
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','mixed_meme')
    require_reviewed_meme(metadata)
    with pytest.raises(ValueError,match='contract_invalid'):
        require_reviewed_meme(dict(metadata,original_story=dict(story,action='unreviewed')))
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','reaction_meme')
    with pytest.raises(ValueError,match='meme_content_unreviewed'): require_reviewed_meme(metadata)


def test_mix_can_produce_football_after_reviewed_clips_are_exhausted(tmp_path,monkeypatch):
    from bamloop.pipeline import prepare
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','mixed_meme')
    monkeypatch.setenv('MEME_DB_PATH',str(tmp_path/'queue.db'))
    monkeypatch.setenv('MEME_OUTPUT_DIR',str(tmp_path))
    monkeypatch.setenv('UNIFIED_YOUTUBE_CHANNEL','false')
    monkeypatch.setenv('PUBLISH_LEDGER_REQUIRED','false')
    with PublishQueue(str(tmp_path/'queue.db'),'bamloop') as queue:
        queue.enqueue('one','meme','global','one','g.mp4',{'meme_category':'global'})
    story=story_bank('football')[0]
    metadata={'title':story['title'],'meme_contract':CONTRACT,'meme_category':'football',
              'story_id':story['id'],'original_story':story,'content_id':identity(story),'content_format':'short'}
    with patch('bamloop.original_meme.build_original_video',return_value=(tmp_path/'f.mp4',metadata)), \
         patch('bamloop.pipeline._validate_short'),patch('bamloop.reaction_meme.build_reaction_video') as stock:
        result=prepare()
    assert result['queued'] and result['meme_category']=='football'
    stock.assert_not_called()


def test_original_bank_exhaustion_does_not_recycle_or_change_category(tmp_path,monkeypatch):
    from bamloop.pipeline import prepare
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','mixed_meme')
    monkeypatch.setenv('MEME_DB_PATH',str(tmp_path/'q.db'))
    monkeypatch.setenv('UNIFIED_YOUTUBE_CHANNEL','false')
    monkeypatch.setenv('PUBLISH_LEDGER_REQUIRED','true')
    with patch('bamloop.pipeline.GitHubLedger') as ledger,patch('bamloop.original_meme.build_original_video') as build:
        ledger.return_value.exists.return_value=True
        result=prepare()
    assert result['reason']=='meme_category_catalog_exhausted'
    build.assert_not_called()


def test_all_actions_have_moving_visuals_and_distinct_story_ids():
    stories=story_bank('football')+story_bank('global')
    assert len({identity(s) for s in stories})==24
    for story in stories:
        assert frame(story,1).tobytes()!=frame(story,5).tobytes()


def test_unified_bamloop_analytics_uses_primary_credentials(monkeypatch):
    from bamloop.performance import _client
    monkeypatch.setenv('UNIFIED_YOUTUBE_CHANNEL','true')
    for suffix in ('CLIENT_ID','CLIENT_SECRET','REFRESH_TOKEN'):
        monkeypatch.setenv('YOUTUBE_'+suffix,'primary-'+suffix)
        monkeypatch.delenv('MEME_YOUTUBE_'+suffix,raising=False)
    with patch('bamloop.performance.Credentials') as credentials,patch('bamloop.performance.build'):
        _client()
    assert credentials.call_args.kwargs['refresh_token']=='primary-REFRESH_TOKEN'


def test_unified_worker_collects_meme_metrics_without_standalone_worker(tmp_path,monkeypatch):
    from production.unified_worker import run_bamloop
    monkeypatch.setenv('UNIFIED_YOUTUBE_CHANNEL','true')
    path=str(tmp_path/'q.db')
    monkeypatch.setenv('NEWS_DB_PATH',path)
    with PublishQueue(path,'bamloop') as queue:
        queue.enqueue('published','meme','done','done','done.mp4',{})
        queue.db.execute("UPDATE publish_queue SET upload_state='published',youtube_video_id='id' WHERE content_id='published'")
        queue.db.commit()
    with patch('bamloop.performance.collect',return_value={'collected':1}) as collect, \
         patch('bamloop.pipeline.publish_pending',return_value={}),patch('bamloop.pipeline.prepare'):
        result=run_bamloop()
    assert result['performance']['collected']==1
    collect.assert_called_once_with(path)


def test_source_slots_interleave_even_with_direct_publishing(tmp_path,monkeypatch):
    monkeypatch.setenv('PUBLISH_DIRECT_ENABLED','true')
    monkeypatch.setenv('VIRAL_PUBLISH_TIMES','09:00,12:00,15:00,18:00,21:00')
    monkeypatch.setenv('BAMLOOP_PUBLISH_TIMES','10:30,13:30,16:30,19:30,22:30')
    monkeypatch.setenv('CHANNEL_TIMEZONE','Europe/Istanbul')
    zone=ZoneInfo('Europe/Istanbul')
    now=datetime(2026,10,6,8,0,tzinfo=zone).timestamp()
    with PublishQueue(str(tmp_path/'q.db'),'viral_futbol') as viral,PublishQueue(str(tmp_path/'q.db'),'bamloop') as bam:
        assert datetime.fromtimestamp(viral.next_slot(now),zone).strftime('%H:%M')=='09:00'
        assert datetime.fromtimestamp(bam.next_slot(now),zone).strftime('%H:%M')=='10:30'
        late=datetime(2026,10,6,11,15,tzinfo=zone).timestamp()
        assert datetime.fromtimestamp(bam.next_slot(late),zone).strftime('%H:%M')=='13:30'


def test_comparisons_preserve_equal_age_and_do_not_invent_qualified_views(tmp_path):
    path=str(tmp_path/'q.db')
    record_snapshot(path,'one',lane='global_meme',sample=PerformanceSample('one',100,age_hours=49))
    record_snapshot(path,'one',lane='global_meme',sample=PerformanceSample('one',9000,age_hours=59))
    record_snapshot(path,'old',lane='football_news',sample=PerformanceSample('old',1000000,age_hours=400))
    data=report(path)
    assert data['lanes']['global_meme']['48h']['median_public_views']==100
    assert data['lanes']['football_news']['48h']['samples']==0
    assert data['ypp']['qualified_views'] is None
    assert data['ypp']['required_daily'] is None
    manual=report(path,qualified_views=4100,subscribers=292)
    assert manual['ypp']['remaining']==2995900
    assert manual['ypp']['subscribers_remaining']==208
