"""Pure tests for archived Stage23D offline verifier."""
import json,unittest
from stage23d_source_provenance import extract_model_rates

class TestModelFs(unittest.TestCase):
    def make(self,fs=48000,nested=(48000,48000)):
        return {'sample_rate':fs,'config':{'submodels':[{'model':{'sample_rate':s}} for s in nested]}}
    def test_both_48k(self):
        self.assertEqual(extract_model_rates(self.make()),(48000,[48000,48000]))
    def test_non_48k_not_silently_overwritten(self):
        self.assertEqual(extract_model_rates(self.make(44100,(44100,44100))),(44100,[44100,44100]))
    def test_submodel_differences_visible(self):
        self.assertEqual(extract_model_rates(self.make(48000,(48000,44100))),(48000,[48000,44100]))
    def test_absent_submodel_fails(self):
        with self.assertRaises(ValueError):extract_model_rates(self.make(48000,()))
    def test_missing_root_fails(self):
        x=self.make();del x['sample_rate']
        with self.assertRaises(KeyError):extract_model_rates(x)
if __name__=='__main__':unittest.main()
