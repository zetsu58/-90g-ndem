from datetime import datetime, timezone
from unittest import TestCase

from viral_futbol.service import Story
from viral_futbol.service_v2 import _effective_trend_gate
from viral_futbol.viral_engine import evaluate_cluster


class QuietNewsFallbackTests(TestCase):
    def test_trustworthy_story_can_pass_quiet_cycle(self):
        cluster = [Story('Takım yeni sezon formasını tanıttı', 'TRT Spor',
                         'https://example.com/story', datetime.now(timezone.utc))]
        score = evaluate_cluster(cluster).score.score
        self.assertEqual(_effective_trend_gate([cluster], score + 1), score)

    def test_suspicious_story_cannot_lower_gate(self):
        cluster = [Story('Oyuncu ayrıldı iddiası', 'Rastgele Hesap',
                         'https://x.com/example/status/1', datetime.now(timezone.utc))]
        self.assertEqual(_effective_trend_gate([cluster], 25), 25)
