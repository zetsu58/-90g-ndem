from __future__ import annotations

import json
import os
import time

from bamloop.engine import build_video, choose_idea
from bamloop.youtube import credentials_ready, upload


def cycle() -> dict:
    idea = choose_idea(str(time.time_ns()))
    video, metadata = build_video(idea, os.getenv("MEME_OUTPUT_DIR", "storage/bamloop"))
    result = {"video": str(video), "metadata": metadata, "uploaded": False, "video_id": None}
    if credentials_ready():
        result["video_id"] = upload(video, metadata)
        result["uploaded"] = True
    return result


if __name__ == "__main__":
    print(json.dumps(cycle(), ensure_ascii=False, indent=2))
