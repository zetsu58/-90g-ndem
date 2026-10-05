import base64
import json
from datetime import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo
import pytest
from production.github_ledger import GitHubLedger, LedgerCapacity, LedgerError

CHANNEL = 'UC'+'A'*22


def setup_ledger(monkeypatch):
    monkeypatch.setenv('GITHUB_LEDGER_TOKEN','fixture')
    monkeypatch.setenv('MAX_SHORTS_PER_DAY','5')
    monkeypatch.setenv('MIN_HOURS_BETWEEN_SHORTS','3')
    monkeypatch.setenv('UNIFIED_YOUTUBE_CHANNEL','false')
    ledger=GitHubLedger()
    items={}
    def request(method,path,data=None):
        if method=='GET':
            if path in items:return items[path]
            children=[{'name':p[len(path)+1:]} for p in items if p.startswith(path+'/') and '/' not in p[len(path)+1:]]
            return children or None
        items[path]={'sha':str(len(items)), 'content':data['content']}
        return items[path]
    ledger._request=request
    now=datetime(2026,10,5,21,tzinfo=ZoneInfo('Europe/Istanbul')).timestamp()
    for i in range(5):
        at=now-(5-i)*10800
        with patch('production.github_ledger.time.time',return_value=at):
            ledger.reserve('viral_futbol',f'item{i}')
            ledger.published('viral_futbol',f'item{i}',f'video{i:06d}')
    return ledger,items,now


def video(i,stamp,*,privacy='public',duration='PT30S',width=720,height=1280):
    return {'id':f'video{i:06d}', 'snippet':{'channelId':CHANNEL,'publishedAt':datetime.fromtimestamp(stamp,ZoneInfo('UTC')).isoformat()},
            'status':{'privacyStatus':privacy},'contentDetails':{'duration':duration},
            'fileDetails':{'videoStreams':[{'widthPixels':width,'heightPixels':height}]}}


def test_three_removed_uploads_do_not_block_two_actual_public_shorts(monkeypatch):
    ledger,items,now=setup_ledger(monkeypatch)
    client=Mock()
    client.videos.return_value.list.return_value.execute.return_value={'items':[video(3,now-21600),video(4,now-10800)]}
    before=set(items)
    with patch('production.youtube_auth.authorized_client',return_value=client),patch('production.github_ledger.time.time',return_value=now):
        audit=ledger.audit_capacity('viral_futbol',object(),CHANNEL)
        assert audit['public_shorts_today']==2
        assert audit['unavailable_recorded_uploads']==3
        assert ledger.reserve('viral_futbol','fresh')
        assert not ledger.reserve('viral_futbol','item0')
    assert before <= set(items)  # No deletion or resurrection of historical identity.


def test_unknown_reservation_and_nonpublic_uploads_are_distinct(monkeypatch):
    ledger,items,now=setup_ledger(monkeypatch)
    path=ledger._item_path('viral_futbol','item0')
    items[path]['content']=base64.b64encode(json.dumps({'state':'reserved'}).encode()).decode()
    client=Mock()
    client.videos.return_value.list.return_value.execute.return_value={'items':[video(1,now-43200,privacy='private'),video(4,now-10800)]}
    with patch('production.youtube_auth.authorized_client',return_value=client),patch('production.github_ledger.time.time',return_value=now):
        audit=ledger.audit_capacity('viral_futbol',object(),CHANNEL)
        assert audit['unresolved_reservations']==1
        assert audit['nonpublic_or_other_channel_uploads']==1
        assert len(ledger._slots('viral_futbol',now))==2


def test_owner_api_failure_cannot_free_quota(monkeypatch):
    ledger,items,now=setup_ledger(monkeypatch)
    client=Mock()
    client.videos.return_value.list.return_value.execute.side_effect=TimeoutError()
    with patch('production.youtube_auth.authorized_client',return_value=client),patch('production.github_ledger.time.time',return_value=now):
        with pytest.raises(LedgerError,match='audit unavailable'):
            ledger.audit_capacity('viral_futbol',object(),CHANNEL)
        with pytest.raises(LedgerCapacity,match='daily'):
            ledger.reserve('viral_futbol','fresh')


def test_real_format_and_new_reservations_still_enforce_limits(monkeypatch):
    ledger,items,now=setup_ledger(monkeypatch)
    client=Mock()
    client.videos.return_value.list.return_value.execute.return_value={'items':[video(0,now-54000,duration='PT4M'),video(1,now-43200,width=1280,height=720),video(4,now-10800)]}
    monkeypatch.setenv('MAX_SHORTS_PER_DAY','2')
    with patch('production.youtube_auth.authorized_client',return_value=client),patch('production.github_ledger.time.time',return_value=now):
        audit=ledger.audit_capacity('viral_futbol',object(),CHANNEL)
        assert audit['public_shorts_today']==1
        assert audit['public_videos_today']==2
        assert audit['corrected_format_records']==2
        assert ledger.reserve('viral_futbol','fresh')
        with pytest.raises(LedgerCapacity,match='daily'):
            ledger.reserve('viral_futbol','another')
