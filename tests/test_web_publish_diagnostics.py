import os
from unittest.mock import patch

from viral_futbol.config import Settings
from viral_futbol.web import public_status
from production.queue import PublishQueue


def test_status_sanitizes_upload_error_and_exposes_effective_gate(tmp_path):
    db = str(tmp_path / 'state.sqlite3')
    with patch.dict(os.environ, {'NEWS_DB_PATH': db, 'SHORTS_MIN_WIDTH': '720', 'SHORTS_MIN_HEIGHT': '1280',
                              'YOUTUBE_REFRESH_TOKEN': 'private-refresh-token', 'RENDER_GIT_COMMIT': 'f' * 40}):
        with PublishQueue(db, 'viral_futbol') as queue:
            queue.enqueue('real-id', 'football', 'Example', 'real-id', '/tmp/example.mp4', {})
            queue.reject('real-id', 'https://example.invalid/?token=private-refresh-token')
        with patch('viral_futbol.web.Settings', return_value=Settings(db_path=db)):
            status = public_status()
        assert status['last_upload_state'] == 'quality_blocked'
        assert status['last_upload_error_type'] == 'UploadOrLedgerError'
        assert status['deploy_commit'] == 'f' * 40
        assert status['configuration']['shorts_min_width'] == '720'
        assert 'private-refresh-token' not in str(status)
