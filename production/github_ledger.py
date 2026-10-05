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

PUBLICATION_AUDIT = {}


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
        from production.publishing_policy import capacity_channel
        channel = capacity_channel(channel)
        audited = getattr(self, '_audited_capacity', None)
        if audited and audited['channel'] == channel and time.time() - audited['checked_at'] < 60:
            return [dict(slot) for slot in audited['slots']]
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
                format_name = name.split('-', 2)[1] if len(name.split('-', 2)) == 3 else 'short'
                if format_name not in {'short', 'video'}:
                    raise LedgerError('Malformed ledger slot format; upload stopped')
                entries.append({'at': stamp, 'day': f'{date:%Y-%m-%d}', 'content_format': format_name,
                                'item_hash': name.removesuffix('.json').split('-')[-1]})
        return entries

    def audit_capacity(self, channel: str, credentials, expected_channel_id: str) -> dict:
        """Count actual public uploads; never erase reservations or duplicate records.

        Call only after channel_preflight. A successful owner API response can
        prove a recorded upload is unavailable/nonpublic. API/ledger failures
        stop publication rather than releasing slots on a failed lookup.
        """
        import base64
        import re
        from production.youtube_auth import authorized_client
        from production.publishing_policy import capacity_channel
        now = time.time()
        raw = self._slots(channel, now)
        resolved = []
        pending = []
        for slot in raw:
            key = slot.get('item_hash', '')
            if not re.fullmatch(r'[0-9a-f]{64}', key):
                raise LedgerError('Invalid capacity item key')
            item = self._request('GET', f'publish-ledger/{channel}/items/{key[:2]}/{key}.json')
            if item is None:
                # Shared legacy namespaces may contain another source's marker.
                alternate = 'bamloop' if channel == 'viral_futbol' else 'viral_futbol'
                item = self._request('GET', f'publish-ledger/{alternate}/items/{key[:2]}/{key}.json')
            try:
                data = json.loads(base64.b64decode(item['content'])) if item else {}
            except (KeyError, ValueError, TypeError):
                raise LedgerError('Invalid publication item') from None
            video_id = data.get('youtube_video_id')
            if data.get('state') == 'published' and isinstance(video_id, str) and re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                resolved.append((slot, video_id))
            else:
                # Unknown/interrupted uploads still occupy their original slot.
                pending.append(slot)
        videos = {}
        ids = sorted({video_id for _, video_id in resolved})
        for offset in range(0, len(ids), 50):
            try:
                response = authorized_client(credentials).videos().list(
                    part='id,snippet,status,contentDetails,fileDetails', id=','.join(ids[offset:offset+50])).execute()
            except Exception:
                raise LedgerError('YouTube capacity audit unavailable') from None
            if not isinstance(response.get('items'), list):
                raise LedgerError('Invalid YouTube capacity audit response')
            videos.update({video['id']:video for video in response['items']})
        occupied = list(pending)
        unavailable = nonpublic = format_corrected = 0
        public_shorts = []
        public_videos = []
        seen = set()
        today = self._today(now)
        for slot, video_id in resolved:
            video = videos.get(video_id)
            if not video:
                unavailable += 1
                continue
            snippet = video.get('snippet') or {}
            status = video.get('status') or {}
            if snippet.get('channelId') != expected_channel_id or status.get('privacyStatus') != 'public':
                nonpublic += 1
                continue
            if video_id in seen:
                continue
            seen.add(video_id)
            stamp = datetime.fromisoformat(snippet['publishedAt'].replace('Z','+00:00')).timestamp()
            duration = (video.get('contentDetails') or {}).get('duration', '')
            match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?', duration)
            seconds = sum(float(value or 0) * factor for value, factor in zip(match.groups(), (3600,60,1))) if match else None
            streams = (video.get('fileDetails') or {}).get('videoStreams') or []
            stream = streams[0] if streams else {}
            width, height = int(stream.get('widthPixels') or 0), int(stream.get('heightPixels') or 0)
            if stream.get('rotation') in {'clockwise','counterClockwise'}:
                width, height = height, width
            # YouTube's current Shorts rule: square/vertical, <= 3 minutes.
            actual_format = slot['content_format']
            if seconds is not None and seconds > 180:
                actual_format = 'video'
            elif width and height:
                actual_format = 'short' if seconds is not None and seconds <= 180 and width <= height else 'video'
            format_corrected += actual_format != slot['content_format']
            actual = dict(slot, at=stamp, day=self._today(stamp), content_format=actual_format)
            occupied.append(actual)
            if actual['day'] == today:
                (public_shorts if actual_format == 'short' else public_videos).append(video_id)
        shorts = [slot for slot in occupied if slot['content_format'] == 'short']
        spacing = max(0.0, float(os.getenv('MIN_HOURS_BETWEEN_SHORTS', '3'))) * 3600
        next_short = max(now, max((slot['at'] for slot in shorts), default=0) + spacing)
        if sum(slot['day'] == today for slot in shorts) >= max(1, int(os.getenv('MAX_SHORTS_PER_DAY', '5'))):
            from datetime import timedelta
            midnight = datetime.fromtimestamp(now, self.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
            next_short = max(next_short, (midnight + timedelta(days=1)).timestamp())
        result = {'checked_at':datetime.fromtimestamp(now,self.timezone).isoformat(),
                  'next_short_slot':datetime.fromtimestamp(next_short,self.timezone).isoformat(),
                  'public_shorts_today':len(public_shorts), 'public_videos_today':len(public_videos),
                  'public_short_ids_today':public_shorts, 'unavailable_recorded_uploads':unavailable,
                  'nonpublic_or_other_channel_uploads':nonpublic, 'corrected_format_records':format_corrected,
                  'unresolved_reservations':len(pending)}
        self._audited_capacity = {'channel':capacity_channel(channel), 'checked_at':time.time(), 'slots':occupied}
        PUBLICATION_AUDIT[channel] = result
        return result

    def reserve(self, channel: str, content_id: str, *, content_format: str = 'short') -> bool:
        if channel not in {'viral_futbol', 'bamloop'}:
            raise LedgerError('Unknown publishing channel')
        if content_format not in {'short', 'video'}:
            raise LedgerError('Unknown content format')
        from production.publishing_policy import require_format, capacity_channel
        require_format(content_format)
        if self.exists(channel, content_id):
            return False
        now = time.time()
        day = self._today(now)
        slots = [slot for slot in self._slots(channel, now) if slot['content_format'] == content_format]
        daily_key = 'MAX_VIDEOS_PER_DAY' if content_format == 'video' else 'MAX_SHORTS_PER_DAY'
        spacing_key = 'MIN_HOURS_BETWEEN_VIDEOS' if content_format == 'video' else 'MIN_HOURS_BETWEEN_SHORTS'
        max_daily = max(1, int(os.getenv(daily_key, '1' if content_format == 'video' else '5')))
        spacing = max(0.0, float(os.getenv(spacing_key, '12' if content_format == 'video' else '3'))) * 3600
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
        marker = f'publish-ledger/{capacity_channel(channel)}/days/{day}/{now:.3f}-{content_format}-{key}.json'
        self._request('PUT', marker, payload)
        audited = getattr(self, '_audited_capacity', None)
        if audited and audited['channel'] == capacity_channel(channel):
            audited['slots'].append({'at':now, 'day':day, 'content_format':content_format, 'item_hash':key})
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
