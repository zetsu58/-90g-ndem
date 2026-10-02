import unittest
from production.longform import plan, narration_budget

class LongFormPlannerTests(unittest.TestCase):
    def test_football_plan_is_landscape_video_contract(self):
        p=plan("Örnek Futbolcu",channel="viral_futbol",facts=["Altyapı dönemi","İlk takım","Transfer"])
        self.assertEqual(p["content_format"],"video")
        self.assertEqual(p["target_seconds"],210)
        self.assertEqual(round(sum(x["duration"] for x in p["scenes"])),210)
        self.assertGreaterEqual(len(p["scenes"]),8)
        self.assertLessEqual(len(p["scenes"]),15)
        self.assertTrue(all(12 <= x["duration"] <= 24 for x in p["scenes"]))

    def test_explainer_plan(self):
        p=plan("Bir teknoloji nasıl çalışır?",channel="bamloop")
        self.assertEqual(p["channel"],"bamloop")
        self.assertEqual(p["scenes"][0]["start"],0)

    def test_word_budget_matches_three_to_four_minutes(self):
        low,high=narration_budget(210)
        self.assertTrue(450 <= low <= 550)
        self.assertTrue(500 <= high <= 600)

    def test_unknown_channel_fails(self):
        with self.assertRaises(ValueError): plan("x",channel="unknown")

if __name__=="__main__": unittest.main()
