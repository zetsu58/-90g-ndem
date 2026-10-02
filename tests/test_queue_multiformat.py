import os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from production.queue import PublishQueue

ENV={"PUBLISH_DIRECT_ENABLED":"true","SMART_PUBLISH_SCHEDULING":"false",
     "MAX_SHORTS_PER_DAY":"1","MAX_VIDEOS_PER_DAY":"1",
     "MIN_HOURS_BETWEEN_SHORTS":"3","MIN_HOURS_BETWEEN_VIDEOS":"12"}

class MultiFormatQueueTests(unittest.TestCase):
    def make(self,root):
        return PublishQueue(str(Path(root)/"q.sqlite3"),"test")

    def add(self,q,cid,fmt):
        return q.enqueue(cid,fmt,"idea-"+cid,"hash-"+cid,"/tmp/"+cid+".mp4",
                         {"content_format":fmt})

    def test_short_does_not_consume_video_quota(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,ENV,clear=False):
            now=time.time()
            with self.make(td) as q:
                self.add(q,"s1","short")
                q.db.execute("UPDATE publish_queue SET upload_state='published',published_at=? WHERE content_id='s1'",(now-60,));q.db.commit()
                self.assertLessEqual(q.next_slot(now,"video"),now+1)

    def test_video_does_not_consume_short_quota(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,ENV,clear=False):
            now=time.time()
            with self.make(td) as q:
                self.add(q,"v1","video")
                q.db.execute("UPDATE publish_queue SET upload_state='published',published_at=? WHERE content_id='v1'",(now-60,));q.db.commit()
                self.assertLessEqual(q.next_slot(now,"short"),now+1)

    def test_claim_skips_blocked_video_and_keeps_short_moving(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,ENV,clear=False):
            now=time.time()
            with self.make(td) as q:
                self.add(q,"published-video","video")
                q.db.execute("UPDATE publish_queue SET upload_state='published',published_at=? WHERE content_id='published-video'",(now-60,))
                self.add(q,"blocked-video","video")
                self.add(q,"ready-short","short")
                q.db.commit()
                claimed=q.claim(now=now)
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["content_id"],"ready-short")

    def test_claim_skips_blocked_short_and_keeps_video_moving(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,ENV,clear=False):
            now=time.time()
            with self.make(td) as q:
                self.add(q,"published-short","short")
                q.db.execute("UPDATE publish_queue SET upload_state='published',published_at=? WHERE content_id='published-short'",(now-60,))
                self.add(q,"blocked-short","short")
                self.add(q,"ready-video","video")
                q.db.commit()
                claimed=q.claim(now=now)
                self.assertIsNotNone(claimed)
                self.assertEqual(claimed["content_id"],"ready-video")

    def test_smart_slot_grace_does_not_skip_just_missed_slot(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,{
            "PUBLISH_DIRECT_ENABLED":"false","SMART_PUBLISH_SCHEDULING":"true",
            "PUBLISH_HOURS":"12","PUBLISH_SLOT_GRACE_MINUTES":"30",
            "CHANNEL_TIMEZONE":"Europe/Istanbul"},clear=False):
            zone=__import__("zoneinfo").ZoneInfo("Europe/Istanbul")
            from datetime import datetime
            now=datetime(2026,10,2,12,10,tzinfo=zone).timestamp()
            with self.make(td) as q:
                self.assertLessEqual(q.next_slot(now,"short"),now+1)

if __name__=="__main__":
    unittest.main()
