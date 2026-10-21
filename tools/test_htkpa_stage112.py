"""Stage112 original-source audit: pure synthetic unit tests; no private data read."""
from __future__ import annotations
import importlib.util
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

GO=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage112/GO.py'
spec=importlib.util.spec_from_file_location('stage112_fixture',GO)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)

class FakeBase:
    FRAMES=20
    RATE=48000
    GAIN=.31
    @staticmethod
    def candidate_floor(x):return max(-32768,min(32767,math.floor(.31*x*32768)))

def vendor(v):return b''.join(struct.pack('<hh',k,k) for k in v)
def f64(v):return b''.join(struct.pack('<d',k) for k in v)
def source_from_pcm_units(q):return f64([v/(.31*32768) for v in q])

class Tests(unittest.TestCase):
    def setUp(self):
        self.base=FakeBase()
        self.y=vendor([0]*20)
        self.di=f64([0.]*20)
        self.output=source_from_pcm_units([0.]*20)

    def test_constants_anchored_to_completed_stage111(self):
        self.assertEqual(M.DI_END_LAST,1344016)
        self.assertEqual(M.PHASES['secondary_0_to_200'],(1488000,1488200))
        self.assertEqual(M.BINS,16)

    def test_pearson_perfect_and_opposite(self):
        self.assertAlmostEqual(M.pearson([1,2,3],[2,4,6]),1.0)
        self.assertAlmostEqual(M.pearson([1,2,3],[-1,-2,-3]),-1.0)

    def test_pearson_degenerate_returns_none(self):
        self.assertIsNone(M.pearson([0,0,0],[1,2,3]))
        self.assertIsNone(M.pearson([1,2],[5,5]))
        with self.assertRaisesRegex(ValueError,'Pearson'):M.pearson([1],[1,2])

    def test_empty_mean_is_null_not_nan(self):
        self.assertIsNone(M.mean_or_none([]))
        self.assertEqual(M.mean_or_none([1.0,3.0]),2.0)

    def test_all_exact_and_zero_DI(self):
        out=M.shape_metrics(self.y,self.output,self.di,0,20,self.base)
        self.assertEqual((out['gt1'],out['mismatches'],out['candidate_di_nonzero_frames']),(0,0,0))
        self.assertEqual(out['residual_rms_lsb'],0)
        self.assertIsNone(out['pearson_signed_integer_residual_vs_candidate_open_slope'])

    def test_residual_signed_events_and_input_nonzero(self):
        raw=source_from_pcm_units([0,2.3,-2.2,.6]+[0]*16)
        di=f64([1,0,1,0]+[0]*16)
        out=M.shape_metrics(self.y,raw,di,0,4,self.base)
        self.assertEqual((out['gt1'],out['gt1_positive'],out['gt1_negative']),(2,1,1))
        self.assertEqual((out['first_gt1_index'],out['last_gt1_index']),(1,2))
        self.assertEqual(out['candidate_di_nonzero_frames'],2)
        self.assertAlmostEqual(out['residual_rms_lsb'],math.sqrt((0+4+9+0)/4))

    def test_top_decile_uses_exact_ceil_ranking(self):
        # 10 frames means one selected frame, maximal first derivative at index 3.
        raw=source_from_pcm_units([0,0,0,10]+[10]*16)
        out=M.shape_metrics(self.y,raw,self.di,0,10,self.base)
        self.assertEqual(out['gt1'],7)
        self.assertEqual(out['top_10pct_frame_count'],1)
        self.assertEqual(out['gt1_in_top_10pct_open_slope'],1)

    def test_first_difference_uses_preceding_sample(self):
        raw=source_from_pcm_units([0,0,9]+[9]*17)
        out=M.shape_metrics(self.y,raw,self.di,2,3,self.base)
        self.assertAlmostEqual(out['candidate_open_slope_mean_abs_lsb_per_frame'],9.0)
        self.assertEqual(out['gt1'],1)

    def test_wrong_buffer_size_rejected(self):
        with self.assertRaisesRegex(ValueError,'byte sizes'):
            M.shape_metrics(b'',self.output,self.di,0,2,self.base)

    def test_stereo_violation_rejected(self):
        y=bytearray(self.y);struct.pack_into('<h',y,4*3+2,10)
        with self.assertRaisesRegex(ValueError,'stereo'):
            M.shape_metrics(bytes(y),self.output,self.di,3,4,self.base)

    def test_nonfinite_open_or_DI_rejected(self):
        for name in ('open','di'):
            raw=[0.]*20;raw[7]=float('inf')
            with self.assertRaisesRegex(ValueError,'nonfinite'):
                M.shape_metrics(self.y,f64(raw) if name=='open' else self.output,
                                f64(raw) if name=='di' else self.di,7,8,self.base)

    def test_invalid_indices_rejected(self):
        for lo,hi in [(5,5),(-1,2),(0,21)]:
            with self.assertRaisesRegex(ValueError,'invalid waveform'):
                M.shape_metrics(self.y,self.output,self.di,lo,hi,self.base)

    def test_bad_prior_status_rejected(self):
        with self.assertRaisesRegex(ValueError,'original private'):
            M.validate_previous({'stage':111,'status':'PENDING'}, {})

    def test_stage111_phase_or_event_contradiction_rejected(self):
        prior={'stage':111,'status':'STAGE111_OFFLINE_EVENT_BOUNDARY_AUDIT_COMPLETED',
          'primary_gt1_total':429,'secondary_gt1_total':33,'global_gt1_over_stage110_scan':462,
          'candidate_di_last_nonzero_index':1344016,
          'primary_gt1_after_di_end':408,
          'phase_summary':{p:{'start':0,'stop_exclusive':1,'mismatches':0,
                              'gt1':0,'candidate_di_nonzero_frames':0} for p in M.PHASES},
          'private_primary_gt1_events':[],'private_secondary_gt1_events':[]}
        verified={k:v for k,v in prior.items()}
        verified['phase_summary']={k:dict(v) for k,v in prior['phase_summary'].items()}
        M.validate_previous(prior,verified)
        verified['phase_summary']['secondary_0_to_200']['gt1']=1
        with self.assertRaisesRegex(ValueError,'phase count contradiction'):
            M.validate_previous(prior,verified)
        verified['phase_summary']['secondary_0_to_200']['gt1']=0
        verified['private_secondary_gt1_events']=[{'index':2,'predicted_minus_vendor_integer':2}]
        with self.assertRaisesRegex(ValueError,'event list contradiction'):
            M.validate_previous(prior,verified)

    def test_no_overwrite_original(self):
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/M.REPORT_NAME;dest.write_text('DO NOT MODIFY')
            with self.assertRaisesRegex(ValueError,'refusing overwrite'):
                M.run(Path(td)/'a.zip',Path(td)/'b.zip',Path(td)/M.STAGE110_NAME,Path(td)/M.STAGE111_NAME,dest)
            self.assertEqual(dest.read_text(),'DO NOT MODIFY')

    def test_canonical_input_names_required(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'canonical report'):
                M.run(Path(td)/'a',Path(td)/'b',Path(td)/'wrong.json',Path(td)/M.STAGE111_NAME,Path(td)/M.REPORT_NAME)

    def test_no_dynamic_runtime_or_model_inference(self):
        text=GO.read_text()
        self.assertNotIn('subprocess',text)
        self.assertNotIn('os.system',text)
        self.assertNotIn('shutil.rmtree',text)
        self.assertIn("output.open('x'",text)
        self.assertIn('gain_lag_or_offset_fitted',text)

if __name__=='__main__':unittest.main()