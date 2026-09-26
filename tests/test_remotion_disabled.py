from pathlib import Path
from unittest.mock import patch

from production.remotion_bridge import render


def test_disabled_remotion_never_starts_node_or_waits(tmp_path, monkeypatch):
    monkeypatch.setenv('REMOTION_ENABLED', 'false')
    with patch('production.remotion_bridge.subprocess.run') as process:
        result = render(output=tmp_path/'unused.mp4', title='x', caption='x',
                        duration=1, kind='meme', media=[Path('missing.png')])
    assert result is False
    process.assert_not_called()
