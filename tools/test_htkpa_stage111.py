"""Stage111 pure synthetic tests only; tests never load private audio/data."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

GO=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage111/GO.py'
sp=importlib.util.spec_from_file_location('fake111',GO)
M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)

class Prev:
    FRAMES=20; RATE=48000; GAIN=0.31; SCAN_START=0
    def candidate_floor(self,x):return max(-32768,min(32767,__import__('math').floor(self.GAIN*x*32768)))

def vendor(v):return b''.join(struct.pack('<hh',k,k) for k in v)
def f64(v):return b''.join(struct.pack('<d',k) for k in v)

class Tests(unittest.TestCase):
    def test_source_constants(self):
        self.assertEqual(M.DI_END_LAST,1344016)
        self.assertEqual(M.PRIMARY_PARENT,(1340000,1360000))
        self.assertEqual(M.BIN,64)
    def test_all_exact(self):
        a=M.event_metrics(vendor([2]*20),f64([2.2/(.31*32768)]*20),f64([0.1]*20),0,20,Prev())
        self.assertEqual((a['mismatches'],a['gt1'],a['candidate_di_nonzero_frames']),(0,0,20))
    def test_large_signed_events(self):
        a=M.event_metrics(vendor([0,0,0,0]),f64([2.3,-2.3,0.3,-.1][i]/(.31*32768) for i in range(4)),f64([0.,0.,.5,0.]),0,4,Prev())
        self.assertEqual(a['gt1'],2)
        self.assertEqual((a['gt1_positive'],a['gt1_negative']),(1,1))
        self.assertEqual((a['first_gt1_index'],a['last_gt1_index']),(0,1))
    def test_stereo_mismatch(self):
        bad=bytearray(vendor([1]*20));struct.pack_into('<h',bad,2,5)
        with self.assertRaisesRegex(ValueError,'stereo'):M.event_metrics(bytes(bad),f64([0]*20),f64([0]*20),0,20,Prev())
    def test_nonfinite(self):
        with self.assertRaisesRegex(ValueError,'nonfinite'):M.event_metrics(vendor([1]*20),f64([0]*20),f64([float('nan')]*20),0,20,Prev())
    def test_invalid_range(self):
        with self.assertRaisesRegex(ValueError,'invalid'):M.event_metrics(b'',b'',b'',20,21,Prev())
    def test_grid_rollup(self):
        with mock.patch.object(M,'BIN',7):
            v=vendor([0]*20);x=f64([0]*20);di=f64([0]*20)
            rows=M.roll_grid(v,x,di,(0,20),Prev())
            self.assertEqual([r['frames'] for r in rows],[7,7,6])
    def test_stage110_missing(self):
        with self.assertRaisesRegex(ValueError,'report status'):
            M.verify_stage110_report({'stage':110,'status':'BROKEN'},b'',b'',b'',Prev())
    def test_report_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'output.json';p.write_text('UNCHANGED')
            with self.assertRaisesRegex(ValueError,'refusing overwrite'):
                M.run(Path(td)/'a',Path(td)/'b',Path(td)/'c',p)
            self.assertEqual(p.read_text(),'UNCHANGED')
    def test_wrong_stage110_name(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'canonical'):
                M.run(Path(td)/'a',Path(td)/'b',Path(td)/'fake.json',Path(td)/'new.json')
    def test_privacy_no_subprocess(self):
        text=GO.read_text()
        self.assertNotIn('subprocess.run',text)
        self.assertNotIn('os.system',text)
        self.assertIn("output.open('x'",text)
    def test_candidate_only(self):
        self.assertIn('vendor_quantizer_gain_resampler_model_fitter_clo_hardware_parity_verified',GO.read_text())

if __name__=='__main__':unittest.main()
