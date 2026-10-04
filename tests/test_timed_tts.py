import unittest
from production.timed_tts import _approximate,_pages

class TimedTTSTests(unittest.TestCase):
    def test_approximate_tokens_cover_audio_monotonically(self):
        tokens=_approximate("Bu gerçek bir belgesel anlatımı örneğidir.",4200)
        self.assertGreaterEqual(len(tokens),6)
        self.assertEqual(tokens[0]["startMs"],0.0)
        self.assertAlmostEqual(tokens[-1]["endMs"],4200,places=1)
        for left,right in zip(tokens,tokens[1:]):
            self.assertLessEqual(left["endMs"],right["startMs"])

    def test_caption_pages_are_short_and_timed(self):
        tokens=_approximate("bir iki üç dört beş altı yedi sekiz dokuz on onbir oniki",6000)
        pages=_pages(tokens,max_words=7,max_span_ms=2600)
        self.assertGreaterEqual(len(pages),2)
        self.assertTrue(all(len(page["text"].split())<=7 for page in pages))
        self.assertTrue(all(page["startMs"]<page["endMs"] for page in pages))

if __name__=="__main__": unittest.main()
