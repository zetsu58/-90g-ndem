from unittest.mock import patch
import pytest
from bamloop.engine import find_licensed_clip


def test_720p_source_is_preferred_and_4k_is_excluded():
    files=[{'width':2160,'height':3840,'link':'4k'},
           {'width':1080,'height':1920,'link':'1080p'},
           {'width':720,'height':1280,'link':'720p'}]
    with patch('bamloop.engine._request_json',return_value={'videos':[{'video_files':files}]}):
        assert find_licensed_clip('fixture','fixture-key')[0]=='720p'


def test_only_unbounded_sources_fail_before_download_or_decode():
    with patch('bamloop.engine._request_json',return_value={'videos':[{'video_files':[{'width':2160,'height':3840,'link':'4k'}]}]}):
        with pytest.raises(RuntimeError,match='No portrait'):
            find_licensed_clip('fixture','fixture-key')
