import json
from unittest.mock import patch
import pytest
from bamloop.meme_catalog import catalog, content_id, require_reviewed_meme, quarantine_legacy, CONTRACT
from production.queue import PublishQueue


def reviewed_metadata():
    clip = catalog()[0]
    return {'meme_contract':CONTRACT, 'clip_id':clip['id'],
            'source_sha256':clip['sha256'], 'reviewed_event':clip['reviewed_event']}


def test_old_stock_and_ai_story_jobs_cannot_consume_retry_or_hide_reviewed_job(tmp_path, monkeypatch):
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','reaction_meme')
    monkeypatch.setenv('MIN_HOURS_BETWEEN_SHORTS','0')
    monkeypatch.setenv('PUBLISH_DIRECT_ENABLED','true')
    with PublishQueue(str(tmp_path/'queue.db'),'bamloop') as queue:
        for i in range(30):
            queue.enqueue(str(i),'meme' if i%2 else 'ai_story','old',str(i),'old.mp4',{'title':'old'})
        queue.enqueue('good','meme','reviewed','good','good.mp4',reviewed_metadata())
        quarantine_legacy(queue)
        row=queue.claim()
        assert row['content_id']=='good'
        assert queue.db.execute("SELECT COUNT(*) FROM publish_queue WHERE upload_state='quality_blocked' AND attempts=0").fetchone()[0]==30


def test_direct_upload_rejects_unreviewed_content_before_oauth(monkeypatch,tmp_path):
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','reaction_meme')
    from bamloop.youtube import upload
    with patch('bamloop.youtube.refresh_credentials') as refresh:
        with pytest.raises(ValueError,match='meme_content_unreviewed'):
            upload(tmp_path/'stock.mp4', {'title':'funny stock','tags':[]})
        refresh.assert_not_called()


def test_same_source_keeps_identity_even_when_caption_changes():
    clip=catalog()[0]
    assert content_id(clip)==content_id(dict(clip,setup='different text',title='different title'))


def test_published_and_inflight_history_is_preserved(tmp_path,monkeypatch):
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','reaction_meme')
    with PublishQueue(str(tmp_path/'queue.db'),'bamloop') as queue:
        for state in ['published','uncertain','uploading']:
            queue.enqueue(state,'meme','old',state,'old.mp4',{})
            queue.db.execute('UPDATE publish_queue SET upload_state=? WHERE content_id=?',(state,state))
        queue.db.commit()
        quarantine_legacy(queue)
        assert {r['upload_state'] for r in queue.recent()}=={'published','uncertain','uploading'}


def test_catalog_exhaustion_defers_without_stock_or_story_fallback(tmp_path,monkeypatch):
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE','reaction_meme')
    monkeypatch.setenv('MEME_DB_PATH',str(tmp_path/'queue.db'))
    monkeypatch.setenv('UNIFIED_YOUTUBE_CHANNEL','false')
    monkeypatch.setenv('PUBLISH_LEDGER_REQUIRED','true')
    from bamloop.pipeline import prepare
    with patch('bamloop.pipeline.GitHubLedger') as ledger, patch('bamloop.pipeline.create_story_video') as story, patch('bamloop.reaction_meme.build_reaction_video') as render:
        ledger.return_value.exists.return_value=True
        assert prepare()['reason']=='reviewed_meme_catalog_exhausted'
        story.assert_not_called()
        render.assert_not_called()


def test_source_hash_mismatch_stops_before_ffmpeg(tmp_path):
    from bamloop.reaction_meme import build_reaction_video
    source=tmp_path/'source.webm'
    source.write_bytes(b'changed file')
    with patch('bamloop.reaction_meme.subprocess.run') as render:
        with pytest.raises(ValueError,match='source changed'):
            build_reaction_video(catalog()[0],str(tmp_path/'render'),local_source=source)
        render.assert_not_called()
