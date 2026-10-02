import unittest
from unittest.mock import patch
from production.longform_narration import fallback_narration,generate_narration

class LongFormNarrationTests(unittest.TestCase):
    def contract(self):
        claims=[f"Doğrulanmış kayıt {i} yılında {2000+i} bilgisini içeriyor." for i in range(12)]
        return {"verified_claims":claims,"min_words":465,"max_words":585,"prompt":"grounded"}
    def test_fallback_meets_three_minute_word_floor(self):
        c=self.contract()
        text=fallback_narration("Konu",c["verified_claims"],c["min_words"],c["max_words"])
        self.assertGreaterEqual(len(text.split()),500)
        self.assertLessEqual(len(text.split()),600)
    def test_generate_falls_back_without_llm(self):
        with patch.dict("os.environ",{"LONGFORM_LLM_BASE_URL":"","LONGFORM_LLM_MODEL":""},clear=False):
            result=generate_narration("Konu",self.contract())
        self.assertEqual(result["provider"],"grounded_fallback")
        self.assertGreaterEqual(result["word_count"],500)

if __name__=="__main__": unittest.main()
