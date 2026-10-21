"""Stage110: synthetic fixture tests only; original proprietary resources not read."""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import wave
from zipfile import ZipFile

CODE=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage110/GO.py'
spec=importlib.util.spec_from_file_location('stage110_synth',CODE)
M=importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

def mk_pcm(data):return b''.join(struct.pack('<hh',v,v) for v in data)
def mk_f64(data):return b''.join(struct.pack('<d',v) for v in data)

class Stage110Tests(unittest.TestCase):
    def test_contract_constants(self):
        self.assertEqual(M.GAIN,.31)
        self.assertEqual((M.SCAN_START,M.SCAN_STOP,M.BIN),(1300000,1500000,1000))
        self.assertEqual(len(M.SILENT),7)
    def test_floor_signed_and_clip(self):
        d=M.GAIN*32768
        self.assertEqual(M.candidate_floor(-1.2/d),-2)
        self.assertEqual(M.candidate_floor(0.8/d),0)
        self.assertEqual(M.candidate_floor(9999),32767)
        self.assertEqual(M.candidate_floor(-9999),-32768)
    def test_reject_nonfinite(self):
        for v in [float('nan'),float('inf'),-float('inf')]:
            with self.assertRaisesRegex(ValueError,'nonfinite'):M.candidate_floor(v)
    def test_metrics_mismatches_gt1_sign_and_di(self):
        vendor=mk_pcm([1,2,3,4,5,6])
        xs=mk_f64([1.5,2.5,6.4,3.2,4.2,6.4])
        di=mk_f64([.1,0,.2,0,0,.3])
        with mock.patch.object(M,'FRAMES',6):
            r=M.metrics_at(vendor,mk_f64([x/(M.GAIN*32768) for x in [1.5,2.5,6.4,3.2,4.2,6.4]]),di,0,6)
        self.assertEqual(r['mismatch_frames'],3)
        self.assertEqual(r['abs_error_gt_1_lsb_frames'],1)
        self.assertEqual(r['max_abs_error_lsb'],3)
        self.assertEqual(r['di_nonzero_frames'],3)
        self.assertEqual((r['first_gt1_index'],r['last_gt1_index']),(2,2))
        self.assertEqual(r['last_nonzero_di_index'],5)
    def test_stereo_disagreement_rejected(self):
        b=bytearray(mk_pcm([0,0,0]));b[2:4]=struct.pack('<h',1)
        with mock.patch.object(M,'FRAMES',3):
            with self.assertRaisesRegex(ValueError,'channel'):M.metrics_at(bytes(b),mk_f64([0]*3),mk_f64([0]*3),0,3)
    def test_nonfinite_di_rejected(self):
        with mock.patch.object(M,'FRAMES',2):
            with self.assertRaisesRegex(ValueError,'nonfinite candidate DI'):M.metrics_at(mk_pcm([0,0]),mk_f64([0,0]),mk_f64([0,float('nan')]),0,2)
    def test_invalid_indices_rejected(self):
        with mock.patch.object(M,'FRAMES',2):
            with self.assertRaisesRegex(ValueError,'indices'):M.metrics_at(b'',b'',b'',1,3)
    def test_allowlist_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.zip'
            with ZipFile(p,'w') as z:z.writestr('bad.txt','b')
            with self.assertRaisesRegex(ValueError,'allowlist'):M.required_zip(p,('expected.json',))
    def test_integrated_mocked_grid_and_reconciliation(self):
        # Tiny 12-sample fit: early [0,4), late [4,12); 2-sample parent bins.
        samples=[0]*12
        predicted=[0,0,0,0,0,0,3,0,0,0,0,0]
        di=[1]*12
        di[8:10]=[0,0]
        s109={'fine_nonzero_di_20k_bins':{str(i):{'floor':{'exact_pcm16_count':(1 if i==6 else 2),'abs_error_gt_1_lsb_frames':(1 if i==6 else 0)}} for i in (0,2,4,6,10)}}
        s105={'fine_20k':{'tiny':{'start':8,'candidate_di_rms':0}}}
        member={'open_nam_prewarm_off.f64le':mk_f64([x/(M.GAIN*32768) for x in predicted]),'open_source_resampled_input_48000.f64le':mk_f64(di)}
        with (mock.patch.multiple(M,FRAMES=12,SCAN_START=4,SCAN_STOP=12,BIN=2,FIT_START=0,FIT_LATE=4,FIT_STOP=12,PARENT_BIN=2,QUASI_IDLE_START=8,SILENT=(8,),HIGHLIGHT_STARTS=(6,),EXPECTED_RECONCILIATION=(4,4,6,5,1,1))):
            r=M.analyze(member,{'stage109_floor_residual_topology_private.json':s109,'stage105_error_topology_private.json':s105},mk_pcm(samples))
        self.assertEqual(len(r['bins_1k']),4)
        self.assertEqual(r['stage109_reconciled']['late_active_gt1'],1)
        self.assertEqual(r['quasi_idle_1420k']['nonzero_di_frames'],0)
        self.assertEqual(r['primary_hotspot_1k'],6)
    def test_reconciliation_rejects_wrong_prior(self):
        samples=[0]*12;member={'open_nam_prewarm_off.f64le':mk_f64([0]*12),'open_source_resampled_input_48000.f64le':mk_f64([0]*12)}
        wrong={'fine_nonzero_di_20k_bins':{str(i):{'floor':{'exact_pcm16_count':0,'abs_error_gt_1_lsb_frames':0}} for i in (0,2,4,6,10)}}
        with mock.patch.multiple(M,FRAMES=12,SCAN_START=4,SCAN_STOP=12,BIN=2,FIT_START=0,FIT_LATE=4,FIT_STOP=12,PARENT_BIN=2,QUASI_IDLE_START=8,SILENT=(8,)):
            with self.assertRaisesRegex(ValueError,'reconciliation'):M.analyze(member,{'stage109_floor_residual_topology_private.json':wrong},mk_pcm(samples))
    def test_no_overwrite_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'exists.json';out.write_text('keep')
            with self.assertRaisesRegex(ValueError,'refusing to overwrite'):M.run(Path(tmp)/'missing.zip',Path(tmp)/'missing.zip',out)
            self.assertEqual(out.read_text(),'keep')
    def test_integrated_run_fake_inputs_single_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'private.json';fake={'status':'done','bins_1k':[1,2], 'value':4}
            with mock.patch.object(M,'read_inputs',return_value=({}, {},b'')),mock.patch.object(M,'analyze',return_value=fake):
                r=M.run(Path(tmp)/'a.zip',Path(tmp)/'b.zip',out)
                self.assertEqual(r['value'],4)
                self.assertNotIn('bins_1k',r)
                self.assertEqual(json.loads(out.read_text())['bins_1k'],[1,2])
                with self.assertRaisesRegex(ValueError,'refusing to overwrite'):M.run(Path(tmp)/'a.zip',Path(tmp)/'b.zip',out)
    def test_source_safety(self):
        s=CODE.read_text()
        self.assertIn("output.open('x'",s)
        self.assertNotIn('subprocess',s)
        self.assertNotIn('requests.',s)
        self.assertNotIn('shutil.rmtree',s)

if __name__=='__main__':unittest.main()