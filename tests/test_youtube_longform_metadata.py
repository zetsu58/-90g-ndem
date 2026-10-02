import unittest
from viral_futbol.youtube_publisher import _metadata

class YouTubeLongFormMetadataTests(unittest.TestCase):
    def test_longform_keeps_video_metadata_without_shorts_rewrite(self):
        title,description,tags=_metadata({
            "content_format":"video",
            "title":"Bir Futbolcunun Kariyeri",
            "description":"Uzun format açıklama\n\nKaynaklar:\n- A",
            "tags":["futbol","kariyer"],
            "language":"tr",
        })
        self.assertEqual(title,"Bir Futbolcunun Kariyeri")
        self.assertIn("Kaynaklar",description)
        self.assertNotIn("#Shorts",description)
        self.assertEqual(tags,["futbol","kariyer"])

if __name__=="__main__": unittest.main()
