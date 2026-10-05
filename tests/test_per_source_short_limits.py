import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
import pytest
from production.queue import PublishQueue
from production.github_ledger import LedgerCapacity
from tests import test_github_ledger as fixtures

ENV={'UNIFIED_YOUTUBE_CHANNEL':'true','PUBLISH_LIMITS_PER_SOURCE':'true',
     'SHORTS_ONLY_MODE':'true','PUBLISH_DIRECT_ENABLED':'true',
     'MAX_SHORTS_PER_DAY':'5','MIN_HOURS_BETWEEN_SHORTS':'3'}

def test_each_source_gets_five_daily_slots_with_three_hour_spacing():
    fixture=fixtures.LedgerTests(); fixture.setUp()
    try:
        now=__import__('datetime').datetime(2026,10,5,0,tzinfo=__import__('zoneinfo').ZoneInfo('Europe/Istanbul')).timestamp()
        with patch.dict(os.environ,ENV):
            for index in range(5):
                with patch('production.github_ledger.time.time',return_value=now+index*10800):
                    for source in ('viral_futbol','bamloop'):
                        assert fixture.ledger.reserve(source,f'{source}-{index}')
                        with pytest.raises(LedgerCapacity):
                            fixture.ledger.reserve(source,f'{source}-too-soon-{index}')
            with patch('production.github_ledger.time.time',return_value=now+15*3600):
                for source in ('viral_futbol','bamloop'):
                    with pytest.raises(LedgerCapacity,match='daily'):
                        fixture.ledger.reserve(source,f'{source}-sixth')
    finally: fixture.doCleanups()

def test_queue_enforces_spacing_separately_while_sharing_database():
    with tempfile.TemporaryDirectory() as root, patch.dict(os.environ,ENV):
        path=str(Path(root)/'q.db'); now=time.time()
        with PublishQueue(path,'viral_futbol') as viral, PublishQueue(path,'bamloop') as bam:
            for queue in (viral,bam):
                for i in range(2):
                    queue.enqueue(str(i),'short','idea',str(i),'/unused.mp4',{})
            assert viral.claim(now=now)
            assert bam.claim(now=now)
            assert viral.claim(now=now) is None
            assert bam.claim(now=now) is None
