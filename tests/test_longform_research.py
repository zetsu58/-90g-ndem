import unittest
from production.longform_research import Evidence,build_fact_manifest
from production.longform_script import build_script

class LongFormResearchTests(unittest.TestCase):
    def evidence(self):
        return [
          Evidence("Olgu bir","Kaynak A"),Evidence("Olgu iki","Kaynak B"),
          Evidence("Olgu üç","Kaynak A"),Evidence("Olgu dört","Kaynak B"),
          Evidence("Olgu beş","Kaynak A"),Evidence("Olgu altı","Kaynak B")]
    def test_manifest_requires_evidence(self):
        with self.assertRaises(ValueError): build_fact_manifest("Konu",self.evidence()[:3])
    def test_manifest_requires_corroboration(self):
        rows=[Evidence(f"Olgu {i}","Tek Kaynak") for i in range(6)]
        with self.assertRaises(ValueError): build_fact_manifest("Konu",rows)
    def test_official_source_can_satisfy_single_source_case(self):
        rows=[Evidence(f"Olgu {i}","Resmi",official=True) for i in range(6)]
        self.assertTrue(build_fact_manifest("Konu",rows)["ready"])
    def test_script_uses_verified_claims_only(self):
        manifest=build_fact_manifest("Konu",self.evidence())
        value=build_script("Konu",manifest)
        self.assertEqual(value["evidence_id"],manifest["id"])
        self.assertEqual(len(value["verified_claims"]),6)
        self.assertTrue(450 <= value["min_words"] <= 550)
        self.assertNotIn("JSON veya sahne etiketi yazma.\n-",value["prompt"][-40:])

if __name__=="__main__": unittest.main()
