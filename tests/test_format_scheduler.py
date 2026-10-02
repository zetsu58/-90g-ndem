import unittest
from production.format_scheduler import decide,channel_kind

class FormatSchedulerTests(unittest.TestCase):
    def test_disabled(self):
        self.assertFalse(decide(now=100,last_longform_at=None,longform_enabled=False).longform)
    def test_due_preserves_shorts(self):
        value=decide(now=100000,last_longform_at=0,longform_enabled=True)
        self.assertTrue(value.shorts)
        self.assertTrue(value.longform)
    def test_rotation(self):
        self.assertEqual(channel_kind("viral_futbol",0),"player_career")
        self.assertEqual(channel_kind("viral_futbol",1),"club_history")
        self.assertEqual(channel_kind("viral_futbol",2),"football_story")
        self.assertEqual(channel_kind("bamloop",0),"explainer")

if __name__=="__main__":
    unittest.main()
