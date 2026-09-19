import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from unittest.mock import patch

from production.queue import PublishQueue
from bamloop.pipeline import select_type
from bamloop.story import LocalStoryProvider, select_providers
from viral_futbol.source_intelligence import confidence_gate
from viral_futbol.service import Story, publisher_family


class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'state.sqlite3')

    def enqueue(self, q, i):
        return q.enqueue(str(i),'meme',f'idea{i}',f'hash{i}',f'/tmp/{i}.mp4',{'title':f'title{i}'})

    def test_independent_channels_and_interval(self):
        with patch.dict(os.environ,{'SMART_PUBLISH_SCHEDULING':'false','PUBLISH_QUEUE_ENABLED':'true'}):
            now=datetime(2026,9,19,6,tzinfo=ZoneInfo('Europe/Istanbul')).timestamp()
            with PublishQueue(self.db,'viral') as a, PublishQueue(self.db,'bamloop') as b:
                for i in range(6): self.enqueue(a,i)
                self.enqueue(b,'other')
                for i in range(5):
                    t=now+i*3*3600
                    row=a.claim(t)
                    self.assertIsNotNone(row)
                    a.published(row['content_id'],f'video{i}',t)
                    self.assertIsNone(a.claim(t+2*3600))
                self.assertEqual(a.counts(now)['videos_today'],5)
                self.assertIsNone(a.claim(now+15*3600))
                self.assertIsNotNone(b.claim(now))
                tomorrow=now+24*3600
                self.assertIsNotNone(a.claim(tomorrow))

    def test_retry_dedup_and_interrupted_upload(self):
        with patch.dict(os.environ,{'SMART_PUBLISH_SCHEDULING':'false'}):
            now=1900000000
            with PublishQueue(self.db,'bamloop') as q:
                self.assertTrue(self.enqueue(q,1))
                self.assertFalse(self.enqueue(q,1))
                row=q.claim(now)
                self.assertIsNotNone(row)
                self.assertIsNone(q.claim(now+5))
                q.failed('1','error',now)
                self.assertIsNone(q.claim(now+50))
                row=q.claim(now+301)
                self.assertIsNotNone(row)
                self.assertRaises(ValueError,q.published,'1','')
                q.published('1','real-id',now+301)
                self.assertIsNone(q.claim(now+20000))
                self.enqueue(q,2)
                q.claim(now+20000)
                q.claim(now+22000)
                state=q.db.execute("SELECT upload_state FROM publish_queue WHERE content_id='2'").fetchone()[0]
                self.assertEqual(state,'uncertain')

    def test_factual_confidence(self):
        dt=datetime.now(ZoneInfo('UTC'))
        def story(title,publisher): return Story(title,'https://news.google.com/x',publisher,dt)
        self.assertTrue(confidence_gate([story('Transfer açıklandı','Reuters')],publisher_family)[0])
        self.assertFalse(confidence_gate([story('Transfer açıklandı','X.com')],publisher_family)[0])
        self.assertEqual(confidence_gate([story('Oyuncu kaldı','Reuters'),story('Oyuncu ayrıldı','BBC')],publisher_family)[1],'conflict')

    def test_single_reputable_source_survives_clustering(self):
        from dataclasses import replace
        from viral_futbol.config import Settings
        from viral_futbol.service import verified_clusters
        settings=Settings(min_sources=2)
        story=Story('Kulüp yeni oyuncuyu açıkladı','https://news.google.com/story','Reuters',datetime.now(ZoneInfo('UTC')))
        self.assertEqual(verified_clusters([story],settings),[])
        clusters=verified_clusters([story],replace(settings,min_sources=1))
        self.assertEqual(len(clusters),1)
        self.assertTrue(confidence_gate(clusters[0],publisher_family)[0])

    def test_alternation_and_provider(self):
        self.assertEqual(select_type([{'content_type':'ai_story'}]*3),'meme')
        self.assertEqual(select_providers(None)[2],'local')
        self.assertEqual(len(LocalStoryProvider().create('seed').scenes),4)
        with patch.dict(os.environ,{'BAMLOOP_IMAGE_PROVIDER':'expensive','BAMLOOP_DAILY_AI_BUDGET_USD':'0'}):
            self.assertEqual(select_providers(None)[2],'local')
        with patch.dict(os.environ,{'BAMLOOP_IMAGE_PROVIDER':'expensive','BAMLOOP_DAILY_AI_BUDGET_USD':'10'}):
            self.assertRaises(RuntimeError,select_providers,None)


if __name__ == '__main__': unittest.main()

class ServiceTests(unittest.TestCase):
    def test_health_head_and_status_without_worker(self):
        import json
        import threading
        from http.server import ThreadingHTTPServer
        from urllib.request import Request, urlopen
        from bamloop.service import Handler as BamHandler
        from viral_futbol.web import Handler as ViralHandler
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MEME_DB_PATH':str(Path(tmp)/'meme.db'),'NEWS_DB_PATH':str(Path(tmp)/'viral.db')}):
            for handler in (BamHandler,ViralHandler):
                server=ThreadingHTTPServer(('127.0.0.1',0),handler)
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                try:
                    for route in ('/','/health','/ready','/status'):
                        with urlopen(Request(f'http://127.0.0.1:{server.server_port}{route}',method='HEAD')) as response:
                            self.assertEqual(response.status,200)
                    with urlopen(f'http://127.0.0.1:{server.server_port}/status') as response:
                        payload=json.load(response)
                    self.assertIn('queue_size',payload)
                finally:
                    server.shutdown();server.server_close();thread.join()

class WorkerIsolationTests(unittest.TestCase):
    def test_bamloop_worker_records_failure_without_raising(self):
        from bamloop import service
        calls=[]
        def sleep(_):
            calls.append(1)
            if len(calls)>1: raise StopIteration()
        with patch.object(service,'cycle',side_effect=RuntimeError('provider failed')),patch.object(service.time,'sleep',side_effect=sleep):
            with self.assertRaises(StopIteration): service.worker()
        self.assertEqual(service.STATE['status'],'error')
        self.assertFalse(service.STATE['running'])
