import json
import os
import shutil
import subprocess
import sys
import types
from unittest.mock import patch

import pytest

from bamloop.meme_catalog import require_reviewed_meme
from bamloop.simulation import (
    CONTRACT, SCENARIOS, _frame, build_simulation_video, scenario_id, scenario_signature,
)


def test_scenarios_have_distinct_durable_identities():
    assert len(SCENARIOS) == 12
    assert len({scenario_id(item) for item in SCENARIOS}) == len(SCENARIOS)
    assert len({scenario_signature(item) for item in SCENARIOS}) == len(SCENARIOS)


def test_simulation_contract_rejects_forged_or_disabled_scene(monkeypatch):
    sample = SCENARIOS[0]
    metadata = {'meme_contract': CONTRACT, 'simulation_id': sample['id'],
                'simulation_signature': scenario_signature(sample), 'content_format': 'short'}
    monkeypatch.setenv('BAMLOOP_CONTENT_MODE', 'reaction_meme')
    monkeypatch.setenv('BAMLOOP_SIMULATION_ENABLED', 'true')
    require_reviewed_meme(metadata)
    with pytest.raises(ValueError, match='meme_content_unreviewed'):
        require_reviewed_meme(dict(metadata, simulation_signature='tampered'))
    with pytest.raises(ValueError, match='meme_content_unreviewed'):
        require_reviewed_meme(dict(metadata, content_format='video'))
    monkeypatch.setenv('BAMLOOP_SIMULATION_ENABLED', 'false')
    with pytest.raises(ValueError, match='meme_content_unreviewed'):
        require_reviewed_meme(metadata)


def test_visual_beats_change_and_result_is_legible():
    scenario = SCENARIOS[-1]
    assert _frame(.8, scenario).tobytes() != _frame(3.2, scenario).tobytes()
    assert _frame(3.2, scenario).tobytes() != _frame(6.9, scenario).tobytes()
    assert _frame(12.5, scenario).tobytes() != _frame(10.9, scenario).tobytes()


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')
def test_production_encoding_is_short_vertical_with_audio(tmp_path):
    validator = types.ModuleType('viral_futbol.youtube_publisher')
    validator._validate_short = lambda path: None
    with patch.dict(sys.modules, {'viral_futbol.youtube_publisher': validator}):
        video, metadata = build_simulation_video(SCENARIOS[0], str(tmp_path))
    data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                                               'format=duration:stream=codec_name,width,height', '-of', 'json', str(video)]))
    assert 12 <= float(data['format']['duration']) <= 14
    assert any(s.get('codec_name') == 'h264' and s.get('width') == 720 and s.get('height') == 1280
               for s in data['streams'])
    assert any(s.get('codec_name') == 'aac' for s in data['streams'])
    assert metadata['content_format'] == 'short'
