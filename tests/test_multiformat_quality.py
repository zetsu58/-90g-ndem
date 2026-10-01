import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from viral_futbol.youtube_publisher import _validate_video

class MultiFormatQualityGateTests(unittest.TestCase):
    def _probe(self,duration,width,height):
        return {"format":{"duration":str(duration)},"streams":[
            {"codec_type":"video","codec_name":"h264","width":width,"height":height},
            {"codec_type":"audio","codec_name":"aac"}]}

    def _file(self):
        tmp=tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        p=Path(tmp.name)/"fixture.mp4"; p.write_bytes(b"x"*120000); return p

    def test_short_accepts_vertical(self):
        p=self._file()
        with patch("viral_futbol.youtube_publisher._probe",return_value=self._probe(40,720,1280)):
            self.assertEqual(_validate_video(p,"short")["format"],"short")

    def test_long_video_accepts_landscape(self):
        p=self._file()
        with patch("viral_futbol.youtube_publisher._probe",return_value=self._probe(210,1280,720)):
            result=_validate_video(p,"video")
        self.assertEqual(result["duration"],210)

    def test_long_video_rejects_short_duration(self):
        p=self._file()
        with patch("viral_futbol.youtube_publisher._probe",return_value=self._probe(60,1280,720)):
            with self.assertRaises(ValueError): _validate_video(p,"video")

    def test_short_rejects_landscape(self):
        p=self._file()
        with patch("viral_futbol.youtube_publisher._probe",return_value=self._probe(40,1280,720)):
            with self.assertRaises(ValueError): _validate_video(p,"short")

if __name__=="__main__": unittest.main()
