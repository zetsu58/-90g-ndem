import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from viral_futbol import web
from viral_futbol.config import Settings
from viral_futbol.service import (
    Store,
    Story,
    build_payload,
    news_editions,
    publisher_family,
    query_task,
    run_once,
    submit,
    title_similarity,
    verified_clusters,
)
from viral_futbol.web import Handler, VERSION


def _cluster() -> list[Story]:
    now = datetime.now(timezone.utc)
    return [
        Story("Club begins talks with player", "https://a.test/1", "Source A", now),
        Story("Club starts talks with player", "https://b.test/2", "Source B", now),
    ]


def test_similar_headlines_match():
    assert title_similarity(
        "Galatasaray yeni transfer için görüşmelere başladı",
        "Galatasaray transfer görüşmelerine başladı",
    ) > 0.52


def test_cluster_requires_distinct_publishers():
    now = datetime.now(timezone.utc)
    stories = [
        Story(
            "Fenerbahçe yıldız oyuncuyla görüşmelere başladı",
            "https://a.test/1",
            "A Spor",
            now,
        ),
        Story(
            "Fenerbahçe yıldız oyuncu için görüşmelere başladı",
            "https://b.test/2",
            "NTV Spor",
            now,
        ),
    ]
    result = verified_clusters(stories, Settings(min_sources=2, similarity=0.52))
    assert len(result) == 1


def test_same_publisher_is_not_verification():
    now = datetime.now(timezone.utc)
    stories = [
        Story("Beşiktaş yeni transferi açıkladı", "https://a.test/1", "A", now),
        Story("Beşiktaş yeni transferini açıkladı", "https://a.test/2", "A", now),
    ]
    assert verified_clusters(stories, Settings(min_sources=2, similarity=0.52)) == []


def test_sibling_brand_labels_are_one_source():
    assert publisher_family("NTV Haber") == publisher_family("NTVSpor")


def test_default_editions_include_turkish_and_global_english():
    editions = news_editions(Settings())
    assert [(language, country) for language, country, _ in editions] == [
        ("tr", "TR"),
        ("en", "US"),
    ]


def test_english_payload_uses_global_voice_and_fast_quality_profile():
    payload = build_payload(_cluster(), Settings(), "en")
    assert payload["video_language"] == "en"
    assert payload["voice_name"] == "en-US-GuyNeural-Male"
    assert payload["video_clip_duration"] == 5
    assert payload["video_aspect"] == "9:16"
    assert "global English" in payload["video_script_prompt"]


def test_dedupe_key_is_language_specific():
    cluster = _cluster()
    assert Store.story_id(cluster, "tr") != Store.story_id(cluster, "en")


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def read(self):
        return json.dumps(self.payload).encode()


def test_mpt_requests_use_x_api_key(monkeypatch, tmp_path):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        if request.full_url.endswith("/videos"):
            return _Response({"data": {"task_id": "task-123"}})
        return _Response({"data": {"state": 4, "progress": 50}})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    settings = Settings(
        dry_run=False,
        db_path=str(tmp_path / "jobs.sqlite3"),
        mpt_api_key="secret-test-key",
    )

    assert (
        submit(
            {"video_subject": "test"},
            settings,
            idempotency_key="viral-futbol:story-123",
        )
        == "task-123"
    )
    assert query_task("task-123", settings)["state"] == 4
    assert all(
        request.get_header("X-api-key") == "secret-test-key"
        for request in requests
    )
    assert requests[0].get_header("Idempotency-key") == "viral-futbol:story-123"


def test_story_is_complete_only_after_mpt_reports_video(monkeypatch, tmp_path):
    cluster = _cluster()
    settings = Settings(
        dry_run=False,
        languages=("en",),
        global_queries=("football",),
        db_path=str(tmp_path / "jobs.sqlite3"),
        retry_delay_seconds=300,
    )
    monkeypatch.setattr(
        "viral_futbol.service._fetch_queries", lambda *args, **kwargs: cluster
    )
    submitted_payloads = []

    def fake_submit(payload, _settings, **kwargs):
        submitted_payloads.append(payload)
        assert kwargs["idempotency_key"].startswith("viral-futbol:")
        return "task-456"

    monkeypatch.setattr("viral_futbol.service.submit", fake_submit)
    first = run_once(settings)

    assert first["submitted"] == 1
    assert first["completed"] == 0
    assert first["fetched"] == 2
    assert first["recent"] == 2
    assert first["verified"] == 1
    assert first["languages"]["en"]["submitted"] == 1
    assert first["selected"][0]["task_id"] == "task-456"
    with Store(settings.db_path) as store:
        assert store.status_counts() == {"submitted": 1}


    monkeypatch.setattr(
        "viral_futbol.service.query_task",
        lambda *args, **kwargs: {
            "state": 1,
            "progress": 100,
            "videos": ["/tasks/task-456/final-1.mp4"],
        },
    )
    second = run_once(settings)

    assert second["completed"] == 1
    assert second["submitted"] == 0
    assert len(submitted_payloads) == 1
    with Store(settings.db_path) as store:
        assert store.status_counts() == {"complete": 1}


def test_web_routes_normalize_trailing_slashes_and_expose_version(monkeypatch):
    monkeypatch.setattr("viral_futbol.web.public_status", lambda: {"running": False})
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(f"{origin}/health/?probe=1", timeout=2) as response:
            health = json.loads(response.read())
        with urlopen(f"{origin}/version/", timeout=2) as response:
            version = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert health == {"status": "ok", "version": VERSION, "running": False}
    assert version == {"status": "ok", "version": VERSION}


def test_public_status_reports_readiness_without_exposing_secrets(
    monkeypatch, tmp_path
):
    settings = Settings(
        dry_run=True,
        languages=("tr", "en"),
        db_path=str(tmp_path / "jobs.sqlite3"),
        mpt_url="https://mpt.example/api/v1",
        mpt_api_key="do-not-expose",
    )
    monkeypatch.setattr(web, "Settings", lambda: settings)

    status = web.public_status()

    assert status["configuration"]["dry_run"] is True
    assert status["configuration"]["mpt_api_key_configured"] is True
    assert status["configuration"]["idempotency"] == "remote-drive-backed"
    assert "do-not-expose" not in json.dumps(status)


def test_failed_submission_becomes_retryable(monkeypatch, tmp_path):
    cluster = _cluster()
    settings = Settings(
        dry_run=False,
        languages=("en",),
        global_queries=("football",),
        db_path=str(tmp_path / "jobs.sqlite3"),
        retry_delay_seconds=0,
        max_task_attempts=2,
    )
    monkeypatch.setattr(
        "viral_futbol.service._fetch_queries", lambda *args, **kwargs: cluster
    )
    attempts = []

    def flaky_submit(payload, _settings, **kwargs):
        attempts.append(payload)
        assert kwargs["idempotency_key"].startswith("viral-futbol:")
        if len(attempts) == 1:
            raise OSError("temporary tunnel failure")
        return "task-retry"

    monkeypatch.setattr("viral_futbol.service.submit", flaky_submit)

    first = run_once(settings)
    second = run_once(settings)

    assert first["submission_failed"] == 1
    assert second["submitted"] == 1
    assert len(attempts) == 2
    with Store(settings.db_path) as store:
        assert store.status_counts() == {"submitted": 1}


def test_store_reset_reuses_the_same_remote_idempotency_key(monkeypatch, tmp_path):
    cluster = _cluster()
    monkeypatch.setattr(
        "viral_futbol.service._fetch_queries", lambda *args, **kwargs: cluster
    )
    keys = []

    def fake_submit(payload, _settings, **kwargs):
        keys.append(kwargs["idempotency_key"])
        return f"task-{len(keys)}"

    monkeypatch.setattr("viral_futbol.service.submit", fake_submit)
    common = {
        "dry_run": False,
        "languages": ("en",),
        "global_queries": ("football",),
    }

    first = run_once(Settings(db_path=str(tmp_path / "first.sqlite3"), **common))
    second = run_once(Settings(db_path=str(tmp_path / "reset.sqlite3"), **common))

    assert first["submitted"] == second["submitted"] == 1
    assert keys[0] == keys[1]
