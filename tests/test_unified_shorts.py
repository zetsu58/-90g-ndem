import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from production.queue import PublishQueue
from production.github_ledger import GitHubLedger, LedgerCapacity
from production.format_scheduler import decide
from production.publishing_policy import bamloop_env
from tests import test_github_ledger as ledger_fixtures

ENV = {"UNIFIED_YOUTUBE_CHANNEL": "true", "SHORTS_ONLY_MODE": "true",
       "PUBLISH_DIRECT_ENABLED": "true", "MAX_SHORTS_PER_DAY": "5",
       "MIN_HOURS_BETWEEN_SHORTS": "3"}


class UnifiedShortsTests(unittest.TestCase):
    def test_bamloop_uses_only_primary_channel_credentials(self):
        from bamloop.youtube import credentials_ready, verify_channel
        with patch.dict(os.environ, {**ENV, "YOUTUBE_ENABLED": "true",
                "YOUTUBE_CLIENT_ID": "primary", "YOUTUBE_CLIENT_SECRET": "secret",
                "YOUTUBE_REFRESH_TOKEN": "refresh", "YOUTUBE_EXPECTED_CHANNEL_ID": "expected",
                "MEME_YOUTUBE_CLIENT_ID": "old-other-channel"}):
            self.assertTrue(credentials_ready())
            self.assertEqual(bamloop_env("CLIENT_ID"), "primary")
            with patch("bamloop.youtube.channel_preflight", return_value={}) as preflight:
                verify_channel(object())
                self.assertEqual(preflight.call_args.args[1], "expected")
            with patch.dict(os.environ, {"YOUTUBE_REFRESH_TOKEN": "", "MEME_YOUTUBE_REFRESH_TOKEN": "old"}):
                self.assertFalse(credentials_ready())

    def test_old_video_backlog_cannot_hide_or_upload_a_short(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, ENV):
            with PublishQueue(str(Path(root)/"q.db"), "viral_futbol") as queue:
                for index in range(30):
                    queue.enqueue(str(index), "video", "long", str(index), "/old.mp4", {"content_format":"video"})
                queue.enqueue("short", "football", "short", "short", "/short.mp4", {})
                self.assertEqual(queue.claim()["content_id"], "short")
                videos = queue.db.execute("SELECT attempts,upload_state FROM publish_queue WHERE content_type='video'").fetchall()
                self.assertTrue(all(row["attempts"]==0 and row["upload_state"]=="format_disabled" for row in videos))
                self.assertIsNone(queue.next_slot(content_format="video"))

    def test_two_sources_share_atomic_queue_spacing(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, ENV):
            path=str(Path(root)/"q.db")
            with PublishQueue(path, "viral_futbol") as viral, PublishQueue(path, "bamloop") as bam:
                viral.enqueue("football", "football", "football", "football", "/f.mp4", {})
                bam.enqueue("story", "ai_story", "story", "story", "/s.mp4", {})
                self.assertIsNotNone(viral.claim())
                self.assertIsNone(bam.claim())

    def test_daily_quota_counts_both_sources(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {**ENV,"MAX_SHORTS_PER_DAY":"1","MIN_HOURS_BETWEEN_SHORTS":"0"}):
            path=str(Path(root)/"q.db")
            with PublishQueue(path,"viral_futbol") as viral, PublishQueue(path,"bamloop") as bam:
                viral.enqueue("f","football","f","f","/f.mp4",{})
                bam.enqueue("s","ai_story","s","s","/s.mp4",{})
                viral.claim()
                viral.published("f","fixture-id")
                self.assertIsNone(bam.claim())

    def test_force_pair_cannot_reenable_longform(self):
        from scripts.run_worker import cycle
        with patch.dict(os.environ, {**ENV,"X_PUBLISH_ENABLED":"false","VIRAL_FORCE_PAIR_TOKEN":"old-force-command"}), \
             patch("scripts.run_worker.trend_gate",return_value={"top":[]}), \
             patch("scripts.run_worker.run_once_v2",return_value={"fetched":0}), \
             patch("scripts.run_worker.publish_ready",return_value={}), \
             patch("scripts.run_worker.collect_youtube_performance",return_value={}), \
             patch("scripts.run_worker.produce_longform",side_effect=AssertionError("longform ran")), \
             patch("production.unified_worker.run_bamloop",return_value={"prepare":{"queued":True}}):
            result=cycle()
        self.assertFalse(result["formats"]["longform"])
        self.assertTrue(result["bamloop"]["prepare"]["queued"])

    def test_shared_ledger_preserves_deduplication_and_blocks_video(self):
        # Use the existing in-memory GitHub fake; no public fixture upload.
        fixture=ledger_fixtures.LedgerTests()
        fixture.setUp()
        try:
            with patch.dict(os.environ, ENV):
                ledger=fixture.ledger
                self.assertTrue(ledger.reserve("viral_futbol", "football"))
                with self.assertRaises(LedgerCapacity):
                    ledger.reserve("bamloop", "story")
                self.assertFalse(ledger.reserve("viral_futbol", "football"))
                with self.assertRaisesRegex(ValueError, "longform_disabled"):
                    ledger.reserve("bamloop", "video", content_format="video")
                self.assertFalse(ledger.exists("bamloop", "video"))
        finally:
            fixture.doCleanups()

    def test_longform_flags_cannot_bypass_shorts_only(self):
        from production.longform_runtime import produce_once
        from bamloop.youtube import upload
        from viral_futbol.youtube_publisher import _upload
        with patch.dict(os.environ, {**ENV,"LONGFORM_ENABLED":"true"}):
            self.assertFalse(decide(longform_enabled=True).longform)
            for action in (
                lambda: produce_once(channel="viral_futbol",db_path="unused",output_dir="unused"),
                lambda: upload(Path("unused"),{"content_format":"video"}),
                lambda: _upload(Path("unused"),{"content_format":"video"},None),
            ):
                with self.assertRaisesRegex(ValueError,"longform_disabled"):
                    action()

    def test_bamloop_production_failure_keeps_publisher_running(self):
        from production.unified_worker import run_bamloop
        from bamloop.pipeline import db_path
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {**ENV,"NEWS_DB_PATH":str(Path(root)/"q.db")}):
            self.assertEqual(db_path(), str(Path(root)/"q.db"))
            with patch("bamloop.pipeline.prepare", side_effect=RuntimeError("fixture")), patch("bamloop.pipeline.publish_pending", return_value={"uploaded":0}) as publisher:
                result=run_bamloop()
            self.assertEqual(result["prepare"]["error"],"RuntimeError")
            self.assertEqual(publisher.call_count,2)
