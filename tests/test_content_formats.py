import unittest
from production.content_formats import profile, football_longform_brief, explainer_longform_brief

class ContentFormatTests(unittest.TestCase):
    def test_short_profile_preserves_existing_contract(self):
        p=profile("short")
        self.assertEqual((p.min_seconds,p.max_seconds,p.width,p.height,p.orientation),(12,70,720,1280,"vertical"))

    def test_long_video_profile(self):
        p=profile("video")
        self.assertEqual((p.min_seconds,p.max_seconds,p.width,p.height,p.orientation),(150,300,1280,720,"landscape"))
        self.assertEqual(p.target_seconds,210)

    def test_football_brief_totals_three_and_half_minutes(self):
        brief=football_longform_brief("örnek futbolcu")
        self.assertEqual(sum(x["seconds"] for x in brief["sections"]),210)
        self.assertEqual(brief["format"],"video")

    def test_explainer_brief_totals_three_and_half_minutes(self):
        brief=explainer_longform_brief("örnek konu")
        self.assertEqual(sum(x["seconds"] for x in brief["sections"]),210)

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(ValueError): profile("reel")

if __name__ == "__main__": unittest.main()
