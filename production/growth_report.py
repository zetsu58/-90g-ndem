"""Compare equal-age Shorts; public view counts never stand in for YPP views."""
from __future__ import annotations
import json
import math
import sqlite3
from statistics import median

LANES = ('football_news', 'football_meme', 'global_meme')
WINDOWS = {'48h': (48, 60), '7d': (168, 192)}


def record_snapshot(db_path, content_id, *, lane, sample):
    if lane not in LANES:
        raise ValueError('unknown_growth_lane')
    db = sqlite3.connect(db_path, timeout=30)
    try:
        with db:
            db.execute('''CREATE TABLE IF NOT EXISTS growth_snapshots (
                lane TEXT NOT NULL, content_id TEXT NOT NULL, window TEXT NOT NULL,
                views INTEGER NOT NULL, likes INTEGER NOT NULL, comments INTEGER NOT NULL,
                age_hours REAL NOT NULL, PRIMARY KEY(lane,content_id,window))''')
            for window, (lo, hi) in WINDOWS.items():
                if lo <= sample.age_hours <= hi:
                    # Preserve the earliest sample in each age window.
                    db.execute('INSERT OR IGNORE INTO growth_snapshots VALUES(?,?,?,?,?,?,?)',
                               (lane,content_id,window,sample.views,sample.likes,sample.comments,sample.age_hours))
    finally:
        db.close()


def report(db_path, *, qualified_views=None, subscribers=None, days_remaining=90):
    if not 1 <= days_remaining <= 90:
        raise ValueError('days_remaining_must_be_1_to_90')
    if (qualified_views is not None and qualified_views < 0) or (subscribers is not None and subscribers < 0):
        raise ValueError('studio_counters_must_be_nonnegative')
    db = sqlite3.connect(db_path, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        exists=db.execute("SELECT 1 FROM sqlite_master WHERE name='growth_snapshots'").fetchone()
        rows=db.execute('SELECT * FROM growth_snapshots').fetchall() if exists else []
    finally:
        db.close()
    groups={}
    for lane in LANES:
        groups[lane]={}
        for window in WINDOWS:
            measured=[int(r['views']) for r in rows if r['lane']==lane and r['window']==window]
            groups[lane][window]={'samples':len(measured), 'median_public_views':median(measured) if measured else None,
                'mean_public_views':round(sum(measured)/len(measured),1) if measured else None,
                'decision':'insufficient_data' if len(measured)<5 else 'review_with_retention_and_swipe_metrics'}
    remaining=None if qualified_views is None else max(0,3_000_000-int(qualified_views))
    return {'lanes':groups,'ypp':{'qualified_views':qualified_views,'source':'manual_Studio_Earn_counter',
        'remaining':remaining,'required_daily':math.ceil(remaining/days_remaining) if remaining is not None else None,
        'subscribers':subscribers,'subscribers_remaining':max(0,500-int(subscribers)) if subscribers is not None else None},
        'warning':'public_views_are_not_qualified_ypp_views; old views expire from rolling_90_day_window'}


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',required=True)
    parser.add_argument('--qualified-views',type=int)
    parser.add_argument('--subscribers',type=int)
    parser.add_argument('--days-remaining',type=int,default=90)
    args=parser.parse_args()
    print(json.dumps(report(args.db,qualified_views=args.qualified_views,subscribers=args.subscribers,
                            days_remaining=args.days_remaining),ensure_ascii=False,indent=2))


if __name__=='__main__': main()
