"""BAMLOOP adapter for the shared durable scene-learning substrate."""
from __future__ import annotations

import time
from viral_futbol.scene_manifest import SceneManifestStore
from viral_futbol.scene_learning import recommended_scene_creative
from viral_futbol.retention_optimizer import recommended_retention_creative


def remember_story_scenes(db_path: str, content_id: str, story) -> list[dict]:
    """Persist BAMLOOP's native four-scene story without replacing its renderer."""
    scene_seconds = 9.0
    now = time.time()
    with SceneManifestStore(db_path) as store:
        with store.db:
            for index, scene in enumerate(story.scenes):
                store.db.execute("""INSERT INTO scene_manifests
                    (story_id,scene_index,start,duration,kind,subject,motion,transition,metadata,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(story_id,scene_index) DO UPDATE SET
                    start=excluded.start,duration=excluded.duration,kind=excluded.kind,
                    subject=excluded.subject,motion=excluded.motion,transition=excluded.transition,
                    metadata=excluded.metadata,updated_at=excluded.updated_at""",
                    (content_id,index,index*scene_seconds,scene_seconds,"bamloop_story",
                     scene.subject,scene.movement,"cut",
                     '{"channel":"bamloop"}',now))
        return store.scenes(content_id)


def learned_story_advice(db_path: str) -> dict | None:
    advice = recommended_scene_creative(db_path)
    return advice.as_dict() if advice else None


def measured_retention_advice(db_path: str) -> dict | None:
    advice=recommended_retention_creative(db_path)
    return advice.as_dict() if advice else None
