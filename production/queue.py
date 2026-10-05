"""Durable per-channel publishing queue and atomic posting reservations."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


class PublishQueue:
    def __init__(self, path: str, channel: str):
        self.path, self.channel = path, channel
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('''CREATE TABLE IF NOT EXISTS publish_queue (
          channel TEXT NOT NULL, content_id TEXT NOT NULL, content_type TEXT NOT NULL,
          idea TEXT NOT NULL, content_hash TEXT NOT NULL, video_path TEXT NOT NULL,
          metadata TEXT NOT NULL, created_at REAL NOT NULL, rendered_at REAL NOT NULL,
          scheduled_at REAL NOT NULL DEFAULT 0, published_at REAL,
          upload_state TEXT NOT NULL DEFAULT 'queued', youtube_video_id TEXT,
          last_error TEXT, attempts INTEGER NOT NULL DEFAULT 0, next_retry_at REAL NOT NULL DEFAULT 0,
          provider TEXT NOT NULL DEFAULT 'local', estimated_cost REAL NOT NULL DEFAULT 0,
          actual_cost REAL, PRIMARY KEY(channel, content_id))''')
        self.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS queue_hash ON publish_queue(channel, content_hash)')
        self.db.commit()

    def __enter__(self): return self
    def __exit__(self, *_): self.db.close()

    def enqueue(self, content_id, content_type, idea, content_hash, video_path, metadata,
                provider='local', estimated_cost=0, actual_cost=None):
        now = time.time()
        with self.db:
            cursor = self.db.execute('''INSERT OR IGNORE INTO publish_queue
              (channel,content_id,content_type,idea,content_hash,video_path,metadata,created_at,
               rendered_at,provider,estimated_cost,actual_cost) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
              (self.channel, content_id, content_type, idea, content_hash, str(video_path),
               json.dumps(metadata, ensure_ascii=False), now, now, provider, estimated_cost, actual_cost))
            return cursor.rowcount == 1

    def recent(self, limit=12):
        return [dict(row) for row in self.db.execute('SELECT * FROM publish_queue WHERE channel=? ORDER BY created_at DESC LIMIT ?', (self.channel, limit))]

    def _local_day(self, timestamp):
        zone = ZoneInfo(os.getenv('CHANNEL_TIMEZONE', 'Europe/Istanbul'))
        start = datetime.fromtimestamp(timestamp, zone).replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), (start + timedelta(days=1)).timestamp()

    def counts(self, now=None):
        now = time.time() if now is None else now
        start, end = self._local_day(now)
        published = self.db.execute("SELECT COUNT(*) FROM publish_queue WHERE channel=? AND upload_state='published' AND published_at>=? AND published_at<?", (self.channel,start,end)).fetchone()[0]
        pending = self.db.execute("SELECT COUNT(*) FROM publish_queue WHERE channel=? AND upload_state IN ('queued','failed','uploading','uncertain')", (self.channel,)).fetchone()[0]
        return {'videos_today': published, 'queue_size': pending}

    @staticmethod
    def _format_of(row):
        try:
            metadata=json.loads(row["metadata"] or "{}")
        except (TypeError,ValueError,json.JSONDecodeError):
            metadata={}
        return "video" if metadata.get("content_format")=="video" or row["content_type"]=="video" else "short"

    def next_slot(self, now=None, content_format="short"):
        from production.publishing_policy import shorts_only, unified_channel, limits_per_source
        if shorts_only() and content_format != "short":
            return None
        now = time.time() if now is None else now
        start, end = self._local_day(now)
        is_longform = content_format == "video"
        max_daily = max(1, int(os.getenv('MAX_VIDEOS_PER_DAY','1') if is_longform else os.getenv('MAX_SHORTS_PER_DAY','5')))
        spacing = max(0, float(os.getenv('MIN_HOURS_BETWEEN_VIDEOS','12') if is_longform else os.getenv('MIN_HOURS_BETWEEN_SHORTS','3'))) * 3600
        rows = self.db.execute(
            "SELECT content_type,metadata,published_at,scheduled_at,upload_state FROM publish_queue "
            "WHERE channel IN (?,?) AND (published_at>=? OR (upload_state IN ('uploading','uncertain') AND scheduled_at>=?)) "
            "ORDER BY COALESCE(published_at,scheduled_at)",
            (self.channel, ('bamloop' if self.channel == 'viral_futbol' else 'viral_futbol') if unified_channel() and not limits_per_source() and self.channel in {'viral_futbol','bamloop'} else self.channel,start,start),
        ).fetchall()
        same_format=[row for row in rows if self._format_of(row)==content_format]
        occupied=[float(row['published_at'] or row['scheduled_at']) for row in same_format]
        earliest=max(now,max(occupied,default=0)+spacing)
        if len(occupied)>=max_daily:
            earliest=max(earliest,end)
        source_key = {'viral_futbol':'VIRAL_PUBLISH_TIMES','bamloop':'BAMLOOP_PUBLISH_TIMES'}.get(self.channel)
        source_times = os.getenv(source_key, '').strip() if source_key else ''
        if source_times:
            slots=[]
            for value in source_times.split(','):
                try:
                    hour, minute = map(int, value.strip().split(':'))
                except ValueError:
                    raise ValueError('publish_times_require_HH_MM') from None
                if not 0 <= hour <= 23 or not 0 <= minute <= 59:
                    raise ValueError('publish_time_out_of_range')
                slots.append((hour,minute))
            zone=ZoneInfo(os.getenv('CHANNEL_TIMEZONE','Europe/Istanbul'))
            day=datetime.fromtimestamp(earliest,zone).replace(hour=0,minute=0,second=0,microsecond=0)
            grace=max(0,float(os.getenv('PUBLISH_SLOT_GRACE_MINUTES','30')))*60
            for offset in range(3):
                for hour,minute in sorted(set(slots)):
                    candidate=(day+timedelta(days=offset)).replace(hour=hour,minute=minute).timestamp()
                    if candidate <= earliest <= candidate+grace:
                        return earliest
                    if candidate >= earliest:
                        return candidate
        if not direct_publish_enabled() and os.getenv('SMART_PUBLISH_SCHEDULING','true').lower() in {'1','true','yes'}:
            slots=[int(x) for x in os.getenv('PUBLISH_HOURS','9,12,15,18,21').split(',') if x.strip().isdigit() and 0<=int(x)<=23]
            if slots:
                zone=ZoneInfo(os.getenv('CHANNEL_TIMEZONE','Europe/Istanbul'))
                day=datetime.fromtimestamp(earliest,zone).replace(hour=0,minute=0,second=0,microsecond=0)
                try:
                    grace=max(0,float(os.getenv('PUBLISH_SLOT_GRACE_MINUTES','30')))*60
                except ValueError:
                    grace=1800
                for offset in range(3):
                    for hour in sorted(set(slots)):
                        candidate=(day+timedelta(days=offset)).replace(hour=hour).timestamp()
                        if candidate<=earliest<=candidate+grace:
                            return earliest
                        if candidate>=earliest:
                            return candidate
        return earliest

    def claim(self, now=None, max_attempts=4):
        if os.getenv('PUBLISH_QUEUE_ENABLED','true').lower() not in {'1','true','yes'}:
            return None
        now=time.time() if now is None else now
        self.db.execute('BEGIN IMMEDIATE')
        try:
            from production.publishing_policy import shorts_only
            if shorts_only():
                # Keep disabled videos and their files for review; do not consume
                # retries or let old long-form entries hide eligible Shorts.
                for pending in self.db.execute("SELECT * FROM publish_queue WHERE channel=? AND upload_state IN ('queued','failed')", (self.channel,)).fetchall():
                    if self._format_of(pending) == "video":
                        self.db.execute("UPDATE publish_queue SET upload_state='format_disabled',last_error='shorts_only_policy' WHERE channel=? AND content_id=?", (self.channel,pending['content_id']))
            self.db.execute(
                "UPDATE publish_queue SET upload_state='uncertain',last_error='upload interrupted; reconcile YouTube before retry' "
                "WHERE channel=? AND upload_state='uploading' AND scheduled_at<?",
                (self.channel,now-1800),
            )
            candidates=self.db.execute(
                "SELECT * FROM publish_queue WHERE channel=? AND upload_state IN ('queued','failed') "
                "AND attempts<? AND next_retry_at<=? ORDER BY created_at LIMIT 24",
                (self.channel,max_attempts,now),
            ).fetchall()
            row=None
            for candidate in candidates:
                content_format=self._format_of(candidate)
                if self.next_slot(now,content_format)<=now+1:
                    row=candidate
                    break
            if row:
                self.db.execute(
                    "UPDATE publish_queue SET upload_state='uploading',attempts=attempts+1,scheduled_at=?,last_error=NULL "
                    "WHERE channel=? AND content_id=?",
                    (now,self.channel,row['content_id']),
                )
            self.db.commit()
            return dict(row) if row else None
        except BaseException:
            self.db.rollback()
            raise

    def published(self, content_id, video_id, now=None):
        if not video_id: raise ValueError('YouTube video ID required')
        with self.db:
            self.db.execute("UPDATE publish_queue SET upload_state='published',youtube_video_id=?,published_at=?,last_error=NULL WHERE channel=? AND content_id=? AND upload_state='uploading'", (video_id,time.time() if now is None else now,self.channel,content_id))

    def failed(self, content_id, error, now=None):
        now = time.time() if now is None else now
        row = self.db.execute('SELECT attempts FROM publish_queue WHERE channel=? AND content_id=?',(self.channel,content_id)).fetchone()
        delay = min(86400, 300 * 2 ** max(0, (row['attempts'] if row else 1)-1))
        with self.db:
            self.db.execute("UPDATE publish_queue SET upload_state='failed',last_error=?,next_retry_at=? WHERE channel=? AND content_id=? AND upload_state='uploading'", (str(error)[:300],now+delay,self.channel,content_id))

    def defer(self, content_id, retry_at):
        """A scheduled slot does not consume an upload attempt."""
        with self.db:
            self.db.execute("UPDATE publish_queue SET upload_state='queued',attempts=MAX(0,attempts-1),next_retry_at=? WHERE channel=? AND content_id=? AND upload_state='uploading'",(retry_at,self.channel,content_id))

    def reject(self, content_id, error):
        with self.db:
            self.db.execute("UPDATE publish_queue SET upload_state='quality_blocked',last_error=? WHERE channel=? AND content_id=?",(str(error)[:300],self.channel,content_id))


def persistent_render_path(path: str) -> bool:
    """Free Render containers may contain /data without a mounted disk."""
    return path.startswith('/data/') and os.path.ismount('/data')


def direct_publish_enabled() -> bool:
    """Explicit opt-in to same-cycle publishing on ephemeral hosting."""
    return os.getenv('PUBLISH_DIRECT_ENABLED', 'false').casefold() in {'1', 'true', 'yes', 'on'}


def publishing_storage_ready(path: str) -> bool:
    return persistent_render_path(path) or direct_publish_enabled()
