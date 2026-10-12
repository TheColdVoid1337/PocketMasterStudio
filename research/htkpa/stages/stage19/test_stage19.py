"""Standalone isolated Stage-19 invariants; no vendor DLL execution."""
import hashlib, json, math, struct, tempfile, unittest
from pathlib import Path
import numpy as np
from scipy.signal import lfilter
import stage19_source_first as s

class Stage19Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=Path('/mnt/data/htkpa_stage14_work/5868USB.dll').read_bytes()
        cls.source=Path('/mnt/data/htkpa_stage14_work/5868USB.dll')
        cls.asm={}
        for lo,hi in [(0x1800bc6b0,0x1800bd050),(0x1800bd490,0x1800bd950),(0x1800be700,0x1800be830),(0x1800b82b0,0x1800b8430),(0x1800bee00,0x1800beeb0)]:
            cls.asm.update(s.disassembly(cls.source,lo,hi))
        cls.banks,cls.pins=s.extract_banks(cls.raw,cls.asm)
    def test_correct_binary(self):self.assertEqual(hashlib.sha256(self.raw).hexdigest(),s.DLL_HASH)
    def test_three_native_banks(self):self.assertEqual(list(self.banks),[44100,48000,96000])
    def test_50_float32_each(self):self.assertTrue(all(h.size==50 and h.dtype==np.dtype('<f4') for h in self.banks.values()))
    def test_all_table_instructions_pinned(self):self.assertEqual(len(self.pins),70)
    def test_no_nan(self):self.assertTrue(all(np.isfinite(h).all() for h in self.banks.values()))
    def test_different_rate_tables(self):self.assertFalse(np.array_equal(self.banks[44100],self.banks[48000]))
    def test_impulse_is_taps(self):
        for h in self.banks.values():
            impulse=np.zeros(70);impulse[0]=1
            self.assertTrue(np.allclose(lfilter(h.astype(np.float64),[1.],impulse)[:50],h,atol=0,rtol=0))
    def test_zero_audio_zero(self):
        for h in self.banks.values():
            self.assertTrue(np.array_equal(lfilter(h.astype(np.float64),[1.],np.zeros(70)),np.zeros(70)))
    def test_constant_steady_state_sum(self):
        for h in self.banks.values():
            y=lfilter(h.astype(np.float64),[1.],np.ones(100))
            self.assertAlmostEqual(y[-1],float(np.sum(h.astype(np.float64))),places=13)
    def test_reference_zip_models(self):
        import zipfile
        pairs=[('Sonicake Manager Files.zip','50f362c39362e5c18de0b6778cbfc3acfb845ee709dbdd97fd5d937a43b99fd7'),('Sonicake Manager(1).zip','2834c9d3c2dc5835ff7104191aecdeb207fafa104bf16cc076463157b18d504a')]
        for name,expect in pairs:
            with zipfile.ZipFile('/mnt/data/'+name) as z:
                self.assertEqual(hashlib.sha256(z.read('clo/cloFile.clo')).hexdigest(),expect)
    def test_source_same_for_two_models(self):
        import zipfile
        hashes=[]
        for name in ('Sonicake Manager Files.zip','Sonicake Manager(1).zip'):
            with zipfile.ZipFile('/mnt/data/'+name) as z:hashes.append(hashlib.sha256(z.read('wavs/nam_input_wav.wav')).hexdigest())
        self.assertEqual(hashes[0],hashes[1])
    def test_audio_convolution_first_sample(self):
        x,sr,_=s.get_samples(Path('/mnt/data/Sonicake Manager Files.zip'))
        out=lfilter(self.banks[sr].astype(np.float64),[1.],x[:64].astype(np.float64))
        for i in (0,1,2,3):
            expected=sum(float(self.banks[sr][j])*float(x[i-j]) for j in range(i+1))
            self.assertAlmostEqual(out[i],expected,places=12)

if __name__=='__main__': unittest.main(verbosity=2)
