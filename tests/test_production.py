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
        self.assertEqual(confidence_gate([story('Oyuncuyla görüşme iddiası','Yerel Gazete')],publisher_family)[1], 'single_report')
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

    def test_story_fallback_when_clip_provider_missing(self):
        from bamloop.pipeline import prepare
        from bamloop.story import LocalStoryProvider
        story = LocalStoryProvider().create('fallback-fixture')
        env = {'MEME_DB_PATH': self.db, 'MEME_OUTPUT_DIR': self.temp.name,
               'PEXELS_API_KEY': '', 'BAMLOOP_MEME_WEIGHT': '1',
               'BAMLOOP_AI_STORY_WEIGHT': '1'}
        with patch.dict(os.environ, env), \
             patch('bamloop.pipeline.select_type', return_value='meme'), \
             patch('bamloop.pipeline.build_video', side_effect=AssertionError('unlicensed meme')), \
             patch('bamloop.pipeline.create_story_video', return_value=(Path(self.temp.name)/'story.mp4', {'title':'Story'},story,'local',0.0)), \
             patch('bamloop.pipeline._validate_short'):
            result = prepare()
        self.assertTrue(result['queued'])
        self.assertEqual(result['content_type'], 'ai_story')

    def test_direct_mode_ignores_hour_slots_but_preserves_limits(self):
        from production.queue import publishing_storage_ready
        with patch.dict(os.environ, {'PUBLISH_DIRECT_ENABLED':'true', 'SMART_PUBLISH_SCHEDULING':'true',
                                     'PUBLISH_HOURS':'23', 'MIN_HOURS_BETWEEN_SHORTS':'3'}):
            self.assertTrue(publishing_storage_ready(self.db))
            now=datetime(2026,9,19,6,tzinfo=ZoneInfo('Europe/Istanbul')).timestamp()
            with PublishQueue(self.db,'viral_futbol') as queue:
                self.enqueue(queue, 'direct')
                row=queue.claim(now)
                self.assertIsNotNone(row)
                queue.published(row['content_id'],'real-video-id',now)
                self.enqueue(queue, 'next')
                self.assertIsNone(queue.claim(now+60))
                self.assertIsNotNone(queue.claim(now+3*3600))

    def test_direct_bamloop_publishes_only_real_video_id(self):
        from bamloop.pipeline import publish_pending
        env={'MEME_DB_PATH':self.db,'PUBLISH_DIRECT_ENABLED':'true',
             'SMART_PUBLISH_SCHEDULING':'false','MIN_HOURS_BETWEEN_SHORTS':'0'}
        with patch.dict(os.environ,env), PublishQueue(self.db,'bamloop') as queue:
            self.enqueue(queue,'bam-direct')
            with patch('bamloop.pipeline.credentials_ready',return_value=True), \
                 patch('bamloop.pipeline.refresh_credentials', return_value=object()), \
                 patch('bamloop.youtube.verify_channel', return_value={'id':'UC123','title':'test'}), \
                 patch('production.youtube_auth.verify_public_upload',return_value=True), \
                 patch('bamloop.pipeline._validate_video',return_value={'duration':30}), \
                 patch('bamloop.pipeline.upload',return_value='real-bam-id'):
                self.assertEqual(publish_pending()['uploaded'],1)
            row=queue.db.execute("SELECT youtube_video_id,upload_state FROM publish_queue WHERE content_id='bam-direct'").fetchone()
            self.assertEqual(tuple(row),('real-bam-id','published'))

    def test_bamloop_refresh_failure_does_not_reserve_ledger(self):
        from bamloop.pipeline import publish_pending
        with patch.dict(os.environ, {'MEME_DB_PATH':self.db,'PUBLISH_DIRECT_ENABLED':'true'}), \
             PublishQueue(self.db,'bamloop') as queue:
            self.enqueue(queue,'oauth-failure')
            with patch('bamloop.pipeline.credentials_ready',return_value=True), \
                 patch('bamloop.pipeline._validate_video',return_value={'duration':30}), \
                 patch('bamloop.pipeline.refresh_credentials', side_effect=RuntimeError('invalid_grant')), \
                 patch('bamloop.pipeline.GitHubLedger') as ledger, \
                 patch('bamloop.pipeline.upload') as upload:
                result=publish_pending()
            self.assertEqual(result['upload_failed'],1)
            ledger.return_value.reserve.assert_not_called()
            upload.assert_not_called()

    def test_direct_viral_publishes_completed_render(self):
        from viral_futbol.config import Settings
        from viral_futbol.service import Store
        from viral_futbol.youtube_publisher import PublicationStore, publish_ready
        env={'NEWS_DB_PATH':self.db,'PUBLISH_DIRECT_ENABLED':'true',
             'SMART_PUBLISH_SCHEDULING':'false','MIN_HOURS_BETWEEN_SHORTS':'0',
             'YOUTUBE_ENABLED':'true','YOUTUBE_CLIENT_ID':'fixture',
             'YOUTUBE_CLIENT_SECRET':'fixture','YOUTUBE_REFRESH_TOKEN':'fixture'}
        with patch.dict(os.environ,env):
            with Store(self.db) as store:
                self.assertTrue(store.reserve('viral-direct','tr',max_attempts=3,stale_seconds=60))
                store.mark_complete('viral-direct','file:///unused.mp4')
            with PublicationStore(self.db) as manifests:
                manifests.remember('viral-direct','Kulüp oyuncuyu duyurdu','tr',['Kulüp'])
            with patch('viral_futbol.youtube_publisher._download'), \
                 patch('viral_futbol.youtube_publisher._validate_video',return_value={'duration':30}), \
                 patch('viral_futbol.youtube_publisher._media_credits',return_value=[{'page':'https://commons.wikimedia.org/wiki/File:A'},{'page':'https://commons.wikimedia.org/wiki/File:B'}]), \
                 patch('viral_futbol.youtube_publisher._refresh_credentials',return_value=object()), \
                 patch('viral_futbol.youtube_publisher.channel_preflight',return_value={'id':'UC123','title':'test'}), \
                 patch('viral_futbol.youtube_publisher.verify_public_upload',return_value=True), \
                 patch('viral_futbol.youtube_publisher._upload',return_value='real-viral-id'):
                result=publish_ready(Settings(db_path=self.db),limit=1)
            self.assertEqual(result['published'],1)
            with PublishQueue(self.db,'viral_futbol') as queue:
                row=queue.db.execute("SELECT youtube_video_id FROM publish_queue WHERE content_id='viral-direct'").fetchone()
                self.assertEqual(row[0],'real-viral-id')

    def test_viral_refresh_failure_does_not_reserve_ledger(self):
        from viral_futbol.config import Settings
        from viral_futbol.service import Store
        from viral_futbol.youtube_publisher import PublicationStore, publish_ready
        env={'NEWS_DB_PATH':self.db,'PUBLISH_DIRECT_ENABLED':'true','YOUTUBE_ENABLED':'true',
             'YOUTUBE_CLIENT_ID':'fixture','YOUTUBE_CLIENT_SECRET':'fixture','YOUTUBE_REFRESH_TOKEN':'fixture'}
        with patch.dict(os.environ,env):
            with Store(self.db) as store:
                self.assertTrue(store.reserve('auth-reject','tr',max_attempts=3,stale_seconds=60))
                store.mark_complete('auth-reject','file:///unused.mp4')
            with PublicationStore(self.db) as manifests:
                manifests.remember('auth-reject','Gerçek olmayan test başlığı','tr',[])
            with patch('viral_futbol.youtube_publisher._download'), \
                 patch('viral_futbol.youtube_publisher._validate_video',return_value={'duration':30}), \
                 patch('viral_futbol.youtube_publisher._media_credits',return_value=[{'page':'https://commons.wikimedia.org/wiki/File:A'},{'page':'https://commons.wikimedia.org/wiki/File:B'}]), \
                 patch('viral_futbol.youtube_publisher._refresh_credentials',side_effect=RuntimeError('invalid_grant')), \
                 patch('production.github_ledger.GitHubLedger') as ledger, \
                 patch('viral_futbol.youtube_publisher._upload') as upload:
                result=publish_ready(Settings(db_path=self.db),limit=1)
            self.assertEqual(result['failed'],1)
            ledger.return_value.reserve.assert_not_called()
            upload.assert_not_called()

    def test_viral_uploaded_id_survives_ledger_write_failure(self):
        from viral_futbol.config import Settings
        from viral_futbol.service import Store
        from viral_futbol.youtube_publisher import PublicationStore, publish_ready
        from production.github_ledger import LedgerError
        env={'NEWS_DB_PATH':self.db,'PUBLISH_DIRECT_ENABLED':'true','YOUTUBE_ENABLED':'true',
             'YOUTUBE_CLIENT_ID':'fixture','YOUTUBE_CLIENT_SECRET':'fixture','YOUTUBE_REFRESH_TOKEN':'fixture'}
        with patch.dict(os.environ,env):
            with Store(self.db) as store:
                store.reserve('ledger-write-failure','tr',max_attempts=3,stale_seconds=60)
                store.mark_complete('ledger-write-failure','file:///unused.mp4')
            with PublicationStore(self.db) as manifests:
                manifests.remember('ledger-write-failure','Yayın testi','tr',[])
            with patch('viral_futbol.youtube_publisher._download'), \
                 patch('viral_futbol.youtube_publisher._validate_video',return_value={'duration':30}), \
                 patch('viral_futbol.youtube_publisher._media_credits',return_value=[{'page':'https://commons.wikimedia.org/wiki/File:A'},{'page':'https://commons.wikimedia.org/wiki/File:B'}]), \
                 patch('viral_futbol.youtube_publisher._refresh_credentials',return_value=object()), \
                 patch('viral_futbol.youtube_publisher.channel_preflight',return_value={'id':'UC123','title':'test'}), \
                 patch('viral_futbol.youtube_publisher.verify_public_upload',return_value=True), \
                 patch('production.github_ledger.required',return_value=True), \
                 patch('production.github_ledger.ready',return_value=True), \
                 patch('production.github_ledger.GitHubLedger') as ledger, \
                 patch('viral_futbol.youtube_publisher._upload',return_value='actual-response-id'):
                ledger.return_value.reserve.return_value=True
                ledger.return_value.published.side_effect=LedgerError('offline')
                result=publish_ready(Settings(db_path=self.db),limit=1)
            self.assertEqual(result['published'],1)
            self.assertEqual(result['ledger_warning'],'ledger_record_failed')
            with PublishQueue(self.db,'viral_futbol') as queue:
                row=queue.db.execute("SELECT upload_state,youtube_video_id FROM publish_queue WHERE content_id='ledger-write-failure'").fetchone()
                self.assertEqual(tuple(row),('published','actual-response-id'))


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
                    routes=('/','/health','/ready','/status') + (('/healthz','/api/status') if handler is BamHandler else ())
                    for route in routes:
                        with urlopen(Request(f'http://127.0.0.1:{server.server_port}{route}',method='HEAD')) as response:
                            self.assertEqual(response.status,200)
                    with urlopen(f'http://127.0.0.1:{server.server_port}/status') as response:
                        payload=json.load(response)
                    self.assertIn('queue_size',payload)
                    if handler is BamHandler:
                        with urlopen(f'http://127.0.0.1:{server.server_port}/api/status') as response:
                            self.assertEqual(response.status,200)
                            self.assertEqual(json.load(response)['service_version'],payload['service_version'])
                        self.assertNotIn('refresh_token',json.dumps(payload).lower())
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


class OAuthPreflightTests(unittest.TestCase):
    def test_both_publishers_pass_bounded_callable_request(self):
        from bamloop.youtube import refresh_credentials
        from viral_futbol.youtube_publisher import YouTubeConfig, _refresh_credentials
        env={'MEME_YOUTUBE_ENABLED':'true','MEME_YOUTUBE_CLIENT_ID':'test-client',
             'MEME_YOUTUBE_CLIENT_SECRET':'test-secret','MEME_YOUTUBE_REFRESH_TOKEN':'test-token'}
        with patch.dict(os.environ,env), patch('google.oauth2.credentials.Credentials.refresh') as refresh:
            refresh_credentials()
            request=refresh.call_args.args[0]
            self.assertTrue(callable(request))
            self.assertEqual(request.keywords['timeout'],30)
            _refresh_credentials(YouTubeConfig(True,'test-client','test-secret','test-token','public','17',3,30))
            request=refresh.call_args.args[0]
            self.assertTrue(callable(request))
            self.assertEqual(request.keywords['timeout'],30)

class DiskReadinessTests(unittest.TestCase):
    def test_path_requires_actual_mount(self):
        from production.queue import persistent_render_path
        with patch('production.queue.os.path.ismount',return_value=False):
            self.assertFalse(persistent_render_path('/data/queue.sqlite3'))
        with patch('production.queue.os.path.ismount',return_value=True):
            self.assertTrue(persistent_render_path('/data/queue.sqlite3'))
            self.assertFalse(persistent_render_path('storage/queue.sqlite3'))
