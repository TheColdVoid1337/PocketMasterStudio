"""Stage106 synthetic only; never tests real Sonicake operator parity."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

PATH=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage106/GO.py'
S=importlib.util.spec_from_file_location('htkpa_stage106',PATH)
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)


def fake():
    d={'stage':105,'status':'STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED',
       'no_new_inference_or_vendordll':True,'candidate_resampler_vendor_parity_verified':False,
       'vendor_model_byte_identity_verified':False,'vendor_fitter_parity_verified':False,
       'fine_20k':{},'coarse_200k':{}}
    for width,key in ((M.FINE,'fine'),(M.COARSE,'block')):
        for i in range((M.FIT_STOP-M.FIT_START)//width):
            start=M.FIT_START+i*width
            d['fine_20k' if width==M.FINE else 'coarse_200k'][f'{key}_{i+1:02d}']={
              'start':start,'stop_exclusive':start+width,'frames':width,
              'silent_or_degenerate':False,'reference_rms':0.2,
              'open_rms':0.5,'candidate_di_rms':0.001 if start<1_100_000 else 0.3,
              'rms_residual_after_gain':0.002 if start<1_100_000 else 0.00001,
              'relative_rms_residual_after_gain':0.01 if start<1_100_000 else 0.00005}
    return d


class TestStage106(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(len(M.get_windows(fake(),'fine_20k',M.FINE)),60)
        self.assertEqual(len(M.get_windows(fake(),'coarse_200k',M.COARSE)),6)

    def test_math(self):
        r=M.analyze(fake())
        self.assertGreater(r['fraction_per_window_gain_fitted_residual_energy_in_early'],0.99)
        self.assertEqual(r['fraction_reference_squared_energy_in_early'],4/6)
        self.assertGreater(r['candidate_di_rms_ratio_late_over_early'],200)
        self.assertFalse(r['vendor_nam_fitter_parity_verified'])

    def test_top_window(self):
        r=M.analyze(fake())
        self.assertEqual(r['largest_adjacent_20k_relative_residual_drop']['between_absolute_samples'],[1099999,1100000])

    def test_quantization_step(self):
        r=M.energy_stats(M.get_windows(fake(),'coarse_200k',M.COARSE)[:4])
        self.assertAlmostEqual(r['residual_rms_in_pcm16_steps'],0.002*32768)

    def test_spread_rank(self):
        self.assertAlmostEqual(M.rank_correlation([1,2,3],[3,2,1]),-1)
        self.assertAlmostEqual(M.rank_correlation([1,2,3],[1,2,3]),1)
        self.assertIsNone(M.rank_correlation([1,1,1],[1,2,3]))

    def test_broken_status(self):
        d=fake();d['status']='WRONG'
        with self.assertRaisesRegex(ValueError,'provenance'):M.analyze(d)

    def test_broken_fine_range(self):
        d=fake();d['fine_20k']['fine_05']['start']+=1
        with self.assertRaisesRegex(ValueError,'window metadata'):M.analyze(d)

    def test_broken_energy(self):
        d=fake();d['fine_20k']['fine_01']['rms_residual_after_gain']=0.1
        d['fine_20k']['fine_01']['relative_rms_residual_after_gain']=0.5
        with self.assertRaisesRegex(ValueError,'energy contradiction'):M.analyze(d)

    def test_reject_bad_numbers(self):
        for v in (float('nan'),float('inf'),-1,'no',True):
            with self.subTest(v=v):
                d=fake();d['fine_20k']['fine_01']['candidate_di_rms']=v
                with self.assertRaises(ValueError):M.analyze(d)

    def test_guard_existing_dest(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inp=root/'stage105_error_topology_private.json'
            inp.write_text(json.dumps(fake()),encoding='utf-8')
            out=root/'stage106_metrics_audit_private.json'
            out.write_text('existing')
            with mock.patch.object(M,'PRIVATE_ROOT',root):
                with self.assertRaisesRegex(ValueError,'overwrite'):M.run(inp)

    def test_private_only_and_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);inp=root/'stage105_error_topology_private.json'
            inp.write_text(json.dumps(fake()),encoding='utf-8')
            with mock.patch.object(M,'PRIVATE_ROOT',root):
                out=M.run(inp)
                self.assertIn('STAGE106',out['status'])
                self.assertTrue((root/'stage106_metrics_audit_private.json').is_file())
                with self.assertRaisesRegex(ValueError,'overwrite'):M.run(inp)

    def test_no_dsp(self):
        t=PATH.read_text()
        self.assertNotIn('subprocess',t)
        self.assertNotIn('5868USB.dll',t)
        self.assertNotIn('rmtree(',t)

if __name__=='__main__':unittest.main()
