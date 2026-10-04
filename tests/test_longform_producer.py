import tempfile,unittest
from pathlib import Path
from production.longform_producer import prepare_contract,attach_assets
from production.longform_research import Evidence

def evidence():
    return [Evidence("Olgu 1","A"),Evidence("Olgu 2","B"),Evidence("Olgu 3","A"),Evidence("Olgu 4","B"),Evidence("Olgu 5","A")]

class LongFormProducerTests(unittest.TestCase):
    def test_contract_is_not_render_ready_without_assets(self):
        c=prepare_contract(subject="Konu",channel="bamloop",evidence=evidence())
        self.assertTrue(c["ready_for_assets"]); self.assertFalse(c["ready_for_render"])
        self.assertEqual(c["metadata"]["content_format"],"video")

    def test_requires_documentary_media_density(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); media=[]
            for i in range(7):
                p=root/f"{i}.png";p.write_bytes(b"x");media.append(p)
            audio=root/"v.wav";audio.write_bytes(b"x")
            with self.assertRaises(ValueError):
                attach_assets(prepare_contract(subject="Konu",channel="bamloop",evidence=evidence()),media=media,audio=audio)

    def test_eight_real_media_assets_unlock_render(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); media=[]
            for i in range(8):
                p=root/f"{i}.png";p.write_bytes(b"x");media.append(p)
            audio=root/"v.wav";audio.write_bytes(b"x")
            c=attach_assets(prepare_contract(subject="Konu",channel="bamloop",evidence=evidence()),media=media,audio=audio)
            self.assertTrue(c["ready_for_render"]); self.assertEqual(len(c["media"]),8)

if __name__=="__main__": unittest.main()
