import os
import time
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from production.github_ledger import GitHubLedger, LedgerError, LedgerCapacity


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'GITHUB_LEDGER_TOKEN': 'fixture-token',
                                        'MIN_HOURS_BETWEEN_SHORTS': '3', 'MAX_SHORTS_PER_DAY': '5'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.ledger = GitHubLedger()
        self.items = {}

        def request(method, path, data=None):
            if method == 'GET':
                if path in self.items: return self.items[path]
                prefix = path + '/'
                children = [dict(name=k[len(prefix):], sha=v['sha']) for k,v in self.items.items()
                            if k.startswith(prefix) and '/' not in k[len(prefix):]]
                return children or None
            if path in self.items and not (data or {}).get('sha'):
                raise LedgerError('collision')
            self.items[path] = {'sha': str(len(self.items)+1), 'content': data['content']}
            return self.items[path]
        self.ledger._request = request

    def test_reservation_prevents_duplicate_and_respects_spacing(self):
        now = datetime(2026,9,20,10,tzinfo=ZoneInfo('Europe/Istanbul')).timestamp()
        with patch('production.github_ledger.time.time', return_value=now):
            self.assertTrue(self.ledger.reserve('viral_futbol', 'story-1'))
            self.assertFalse(self.ledger.reserve('viral_futbol', 'story-1'))
            with self.assertRaisesRegex(LedgerCapacity, 'spacing'):
                self.ledger.reserve('viral_futbol', 'story-2')
            self.assertTrue(self.ledger.reserve('bamloop','story-2'))
            self.ledger.published('viral_futbol','story-1','real-id')
        with patch('production.github_ledger.time.time', return_value=now+10800):
            self.assertTrue(self.ledger.reserve('viral_futbol','story-2'))

    def test_short_and_video_limits_are_independent(self):
        now = datetime(2026,9,20,6,tzinfo=ZoneInfo('Europe/Istanbul')).timestamp()
        for i in range(5):
            with patch('production.github_ledger.time.time', return_value=now+i*10800):
                self.assertTrue(self.ledger.reserve('bamloop', f'short-{i}'))
        with patch('production.github_ledger.time.time', return_value=now+4*10800):
            self.assertTrue(self.ledger.reserve('bamloop', 'video-1', content_format='video'))
        with patch('production.github_ledger.time.time', return_value=now+5*10800):
            with self.assertRaisesRegex(LedgerCapacity, 'daily'):
                self.ledger.reserve('bamloop', 'video-2', content_format='video')
            with self.assertRaisesRegex(LedgerCapacity, 'daily'):
                self.ledger.reserve('bamloop', 'short-6')

    def test_missing_ledger_token_fails_closed(self):
        with patch.dict(os.environ, {'GITHUB_LEDGER_TOKEN': ''}):
            with self.assertRaises(LedgerError): GitHubLedger()
        with self.assertRaises(LedgerError):
            self.ledger.published('viral_futbol','unknown','')

    def test_daily_limit_and_next_day(self):
        now = datetime(2026,9,20,6,tzinfo=ZoneInfo('Europe/Istanbul')).timestamp()
        for i in range(5):
            with patch('production.github_ledger.time.time',return_value=now+i*10800):
                self.assertTrue(self.ledger.reserve('bamloop',f'item-{i}'))
        with patch('production.github_ledger.time.time',return_value=now+5*10800):
            with self.assertRaisesRegex(LedgerCapacity,'daily') as error:
                self.ledger.reserve('bamloop','item-6')
            self.assertGreater(error.exception.retry_at,now)


if __name__ == '__main__': unittest.main()
