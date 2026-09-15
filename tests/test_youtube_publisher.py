import json
import sqlite3

from viral_futbol.youtube_publisher import PublicationStore, YouTubeConfig, _metadata


def _jobs_table(db_path):
    db = sqlite3.connect(db_path)
    db.execute(
        """
        CREATE TABLE jobs (
            story_id TEXT PRIMARY KEY, language TEXT NOT NULL, task_id TEXT,
            status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT, output_url TEXT, created_at REAL NOT NULL,
            updated_at REAL NOT NULL, next_retry_at REAL NOT NULL DEFAULT 0
        )
        """
    )
    db.execute(
        "INSERT INTO jobs VALUES ('story-1','tr','task-1','complete',1,NULL,"
        "'https://mpt.test/final-1.mp4',1,1,0)"
    )
    db.commit()
    db.close()


def test_youtube_is_disabled_without_explicit_configuration(monkeypatch):
    monkeypatch.delenv("YOUTUBE_ENABLED", raising=False)
    assert YouTubeConfig.from_env().ready is False


def test_manifest_and_publication_are_idempotent(tmp_path):
    path = str(tmp_path / "jobs.sqlite3")
    _jobs_table(path)
    with PublicationStore(path) as store:
        store.remember("story-1", "Galatasaray transferi açıkladı", "tr", ["TFF", "BBC"])
        jobs = store.ready_jobs()
        assert len(jobs) == 1
        assert store.claim("story-1") is True
        assert store.claim("story-1") is False
        store.published("story-1", "youtube-123")
        assert store.ready_jobs() == []
        assert store.counts() == {"published": 1}


def test_metadata_is_short_compatible():
    title, description, tags = _metadata({
        "title": "Galatasaray yeni transferi resmen açıkladı",
        "language": "tr",
        "sources_json": json.dumps(["TFF", "BBC"]),
    })
    assert title.endswith("#Shorts")
    assert len(title) <= 100
    assert "Kaynak yayıncılar: TFF, BBC" in description
    assert "shorts" in tags
