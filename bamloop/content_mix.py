"""Keep football comedy and general memes as separate, measurable lanes."""
from __future__ import annotations

import json
import os

DEFAULT_PATTERN = ("global", "football", "global", "football", "global")


def mixed_mode():
    return os.getenv("BAMLOOP_CONTENT_MODE", "reaction_meme").casefold() == "mixed_meme"


def pattern():
    raw = os.getenv("BAMLOOP_CATEGORY_PATTERN", ",".join(DEFAULT_PATTERN))
    values = tuple(value.strip().casefold() for value in raw.split(","))
    if not values or len(values) > 20 or any(value not in {"football", "global"} for value in values):
        raise ValueError("invalid_bamloop_category_pattern")
    if set(values) != {"football", "global"}:
        raise ValueError("both_football_and_global_memes_required")
    return values


def next_category(queue):
    # Count only new classified jobs, including queued ones. Restarting a worker
    # or waiting for a publishing slot must not reset the category rotation.
    rows = queue.db.execute(
        "SELECT metadata FROM publish_queue WHERE channel='bamloop' "
        "AND upload_state NOT IN ('quality_blocked','format_disabled')"
    ).fetchall()
    count = 0
    for row in rows:
        try:
            category = json.loads(row['metadata']).get('meme_category')
        except (ValueError, TypeError, AttributeError):
            continue
        if category in {"football", "global"}:
            count += 1
    sequence = pattern()
    return sequence[count % len(sequence)], count
