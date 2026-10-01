import unittest
from production.longform_metadata import longform_metadata

class LongFormMetadataTests(unittest.TestCase):
    def test_regular_video_never_gets_shorts_marker(self):
        for channel in ("viral_futbol","bamloop"):
            m=longform_metadata("Örnek başlık",channel,"player_career")
            self.assertEqual(m["content_format"],"video")
            self.assertNotIn("#Shorts",m["title"])
            self.assertNotIn("#Shorts",m["description"])
    def test_title_is_api_safe_length(self):
        self.assertLessEqual(len(longform_metadata("x"*140,"viral_futbol")["title"]),100)

if __name__=="__main__": unittest.main()
