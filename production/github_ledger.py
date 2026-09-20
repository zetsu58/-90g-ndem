"""Private GitHub branch ledger for ephemeral Render publishers.

No credentials, story text or media are stored in this branch. An upload is
reserved before the network call so an interrupted request cannot replay.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo


def required() -> bool:
    return os.getenv('PUBLISH_LEDGER_REQUIRED', 'false').casefold() in {'1', 'true', 'yes', 'on'}


def ready() -> bool:
    return bool(os.getenv('GITHUB_LEDGER_TOKEN', '').strip())


class LedgerError(RuntimeError):
    pass


class LedgerCapacity(LedgerError):
    def __init__(self, message: str, retry_at: float):
        super().__init__(message)
        self.retry_at = retry_at


class GitHubLedger:
    def __init__(self):
        self.token = os.getenv('GITHUB_LEDGER_TOKEN', '').strip()
        self.repo = os.getenv('GITHUB_LEDGER_REPOSITORY', 'zetsu58/-90g-ndem').strip()
        self.branch = os.getenv('GITHUB_LEDGER_BRANCH', 'publish-ledger').strip()
        self.timezone = ZoneInfo(os.getenv('CHANNEL_TIMEZONE', 'Europe/Istanbul'))
        if not self.token or not self.branch or len(self.repo.split('/')) != 2:
            raise LedgerError('GitHub ledger is not configured')

    def _request(self, method: str, path: str, data: dict | None = None):
        url = 'https://api.github.com/repos/' + self.repo + '/contents/' + urllib.parse.quote(path, safe='/')
        if method == 'GET':
            url += '?ref=' + urllib.parse.quote(self.branch, safe='')
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(url, data=body, method=method, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'ViralFutbol-PublishLedger/1',
            'Content-Type': 'application/json',
        })
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and method == 'GET':
                return None
            if exc.code == 422 and method == 'PUT':
                raise LedgerError('GitHub ledger collision; upload stopped') from None
            raise LedgerError(f'GitHub ledger HTTP {exc.code}; upload stopped') from None
        except (TimeoutError, OSError, ValueError):
            raise LedgerError('GitHub ledger unreachable; upload stopped') from None

    @staticmethod
    def _key(content_id: str) -> str:
        return hashlib.sha256(content_id.encode()).hexdigest()

    def _item_path(self, channel: str, content_id: str) -> str:
        key = self._key(content_id)
        return f'publish-ledger/{channel}/items/{key[:2]}/{key}.json'

    def exists(self, channel: str, content_id: str) -> bool:
        return self._request('GET', self._item_path(channel, content_id)) is not None

    def _day_path(self, channel: str, day: str, content_id: str) -> str:
        return f'publish-ledger/{channel}/days/{day}/{self._key(content_id)}.json'

    def _today(self, now: float) -> str:
        return datetime.fromtimestamp(now, self.timezone).strftime('%Y-%m-%d')

    def _slots(self, channel: str, now: float) -> list[dict]:
        day = datetime.fromtimestamp(now, self.timezone)
        previous = datetime.fromtimestamp(now - 86400, self.timezone)
        entries = []
        for date in (previous, day):
            folder = f'publish-ledger/{channel}/days/{date:%Y-%m-%d}'
            for item in self._request('GET', folder) or []:
                # Each day's marker is immutable and records an actual reservation.
                # File name encodes the timestamp as its first component.
                name = str(item.get('name', ''))
                try:
                    stamp = float(name.split('-', 1)[0])
                except ValueError:
                    raise LedgerError('Malformed ledger slot; upload stopped') from None
                entries.append({'at': stamp, 'day': f'{date:%Y-%m-%d}'})
        return entries

    def reserve(self, channel: str, content_id: str) -> bool:
        if channel not in {'viral_futbol', 'bamloop'}:
            raise LedgerError('Unknown publishing channel')
        if self.exists(channel, content_id):
            return False
        now = time.time()
        day = self._today(now)
        slots = self._slots(channel, now)
        max_daily = max(1, int(os.getenv('MAX_SHORTS_PER_DAY', '5')))
        spacing = max(0.0, float(os.getenv('MIN_HOURS_BETWEEN_SHORTS', '3'))) * 3600
        if sum(s['day'] == day for s in slots) >= max_daily:
            next_day = datetime.fromtimestamp(now, self.timezone).replace(hour=0,minute=0,second=0,microsecond=0)
            from datetime import timedelta
            raise LedgerCapacity('Channel daily upload limit reached', (next_day+timedelta(days=1)).timestamp())
        if slots and now - max(s['at'] for s in slots) < spacing:
            raise LedgerCapacity('Channel upload spacing is active', max(s['at'] for s in slots)+spacing)
        import base64
        key = self._key(content_id)
        data = {'content_hash': key, 'state': 'reserved', 'reserved_at': now}
        payload = {'message': f'Reserve {channel} video {key[:12]}', 'branch': self.branch,
                   'content': base64.b64encode(json.dumps(data).encode()).decode()}
        self._request('PUT', self._item_path(channel, content_id), payload)
        # Reserve the slot before attempting the external upload. An index write
        # failure leaves the item reserved, preventing replay after restart.
        marker = f'publish-ledger/{channel}/days/{day}/{now:.3f}-{key}.json'
        self._request('PUT', marker, payload)
        return True

    def published(self, channel: str, content_id: str, video_id: str) -> None:
        if not video_id:
            raise LedgerError('YouTube video ID required')
        import base64
        path = self._item_path(channel, content_id)
        item = self._request('GET', path)
        if item is None:
            raise LedgerError('Missing upload reservation')
        data = {'content_hash': self._key(content_id), 'state': 'published',
                'youtube_video_id': video_id, 'published_at': time.time()}
        self._request('PUT', path, {'message': f'Record {channel} YouTube upload {self._key(content_id)[:12]}',
                                    'branch': self.branch, 'sha': item['sha'],
                                    'content': base64.b64encode(json.dumps(data).encode()).decode()})
