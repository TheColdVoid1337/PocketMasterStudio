"""Stage105 standalone synthetic arithmetic/guard tests, no vendor or NAM runtime."""
from __future__ import annotations
import importlib.util
import json
import struct
from unittest import mock
import math
from pathlib import Path
import tempfile
import unittest

SOURCE=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage105/GO.py'
s=importlib.util.spec_from_file_location('stage105_test',SOURCE)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class Stage105Test(unittest.TestCase):
    def test_const(self):
        self.assertEqual((m.FIT_START,m.FIT_END,m.FINE,m.COARSE,m.MAX_LAG),(300000,1500000,20000,200000,4))

    def test_gain_simple(self):
        x=[1.,2.,-3.,2.,1.]
        y=[a*.31 for a in x]
        r=m.estimate(y,x,0,5)
        self.assertAlmostEqual(r['gain_open_to_manager'],.31)
        self.assertLess(r['relative_rms_residual_after_gain'],1e-7)
        self.assertAlmostEqual(r['zero_lag_cosine_if_lag_zero'],1.)

    def test_gain_plus_dc(self):
        x=[-3.,-2.,-1.,0.,1.,2.,3.]
        y=[.31*a+.02 for a in x]
        r=m.estimate(y,x,0,len(x))
        self.assertAlmostEqual(r['affine_gain_diagnostic'],.31)
        self.assertAlmostEqual(r['dc_offset_diagnostic'],.02)
        self.assertLess(r['relative_rms_residual_after_gain_and_dc'],1.e-7)
        self.assertGreater(r['relative_rms_residual_after_gain'],.01)

    def test_lag_preferred_positive(self):
        x=[0.,1.,0.,0.,2.,0.,0.,-1.,0.,0.,3.,0.,0.,-2.,0.,0.,4.,0.,0.,0.,0.,0.]
        y=[x[i+1]*.31 if i+1<len(x) else 0 for i in range(len(x))]
        r=m.lag_sweep(y,x,0,len(x),max_lag=2)
        self.assertEqual(r['best_integer_lag'],1)
        self.assertGreater(r['zero_lag_relative_rms'],r['best_relative_rms'])

    def test_lag_same_central_domain(self):
        x=[1.,2.,0.,-1.,1.,3.,2.,-1.,2.,0.,1.,3.]
        y=[v*.31 for v in x]
        r=m.lag_sweep(y,x,0,len(x),max_lag=2)
        self.assertEqual((r['common_start'],r['common_stop_exclusive']),(2,10))
        self.assertEqual(r['best_integer_lag'],0)
        self.assertEqual({s['frames'] for s in r['scans']},{8})

    def test_zero_y_handled(self):
        r=m.estimate([0.,0.,0.],[1.,2.,3.],0,3)
        self.assertTrue(r['silent_or_degenerate'])

    def test_invalid_input(self):
        for y,x,a,b in [([1.],[1.,2.],0,1),([1.,2.],[1.,2.],1,1),([1.,2.],[1.,2.],0,4)]:
            with self.assertRaises(ValueError):m.estimate(y,x,a,b)
        with self.assertRaises(ValueError):m.estimate([1.,2.],[1.,2.],0,2,input_signal=[1.])
        with self.assertRaises(ValueError):m.estimate([1.,float('nan')],[1.,2.],0,2)
        with self.assertRaises(ValueError):m.estimate([1.,2.],[1.,2.],0,2,lag=1)

    def test_windows_nonoverlap(self):
        coarse,fine=m.windows()
        self.assertEqual(len(coarse),6);self.assertEqual(len(fine),60)
        self.assertEqual(coarse[0][1],m.FIT_START)
        self.assertEqual(coarse[-1][2],m.FIT_END)
        self.assertTrue(all(fine[i][2]==fine[i+1][1] for i in range(59)))

    def test_source_has_no_mutation_or_inference(self):
        t=SOURCE.read_text()
        for forbidden in ('rmtree(', 'unlink(', 'subprocess.', '5868USB.dll', 's98.run('):
            self.assertNotIn(forbidden,t)
        self.assertIn('refusing to overwrite',t)
        self.assertIn("stage105_error_topology_private.json",t)

    def test_integrated_fake_reports_sha_and_no_overwrite(self):
        """Small complete Stage102/103/104 handoff; no real vendor audio."""
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            work=root/'fake_run'
            work.mkdir()
            N=160
            x=[math.sin(i*0.37)+0.24*math.cos(i*0.17) for i in range(N)]
            y=[0.31*v for v in x]
            candidate=[0.15*v for v in x]
            def write_vals(path,vals):
                path.write_bytes(b''.join(struct.pack('<d',v) for v in vals))
                return m.sha(path)
            hs=write_vals(work/'open_nam_prewarm_off.f64le',x)
            hdi=write_vals(work/'open_source_resampled_input_48000.f64le',candidate)
            report={
                'stage':102,'status':'SOURCE_DERIVED_DI_CANDIDATE_VS_VENDOR_OUTPUT_COMPARISON_COMPLETED',
                'frames_compared_from_start':N,'vendor_resampler_parity_verified':False,
                'di_44100_pcm16_identical':True,
                'resampled_input_sha256':hdi,
                'conditions':{'off':{'open_output_sha256':hs}},
            }
            (work/'comparison_private.json').write_text(json.dumps(report))
            blocks={}
            for i,start in enumerate(range(20,140,20)):
                val=m.estimate(y,x,start,start+20)
                blocks[f'fit_block_{i+1:02d}_{start}_{start+20}']={
                    'gain_open_to_manager_least_squares':val['gain_open_to_manager']}
            stage103={'stage':103,'status':'STAGE103_OFFLINE_GAIN_WINDOW_DIAGNOSTIC_COMPLETED',
                'conditions':{'off':{'open_output_sha256':hs,'metrics':blocks}}}
            stage104={'stage':104,'status':'STAGE104_OFFLINE_PREWARM_DIFFERENCE_LOCALIZED',
                'ranges':{'fit_full_300k_1500k':{'bitwise_equal':True,'different_f64_word_count':0}},
                'raw_output_sha256':{'off':hs}}
            (work/'stage103_gain_audit_private.json').write_text(json.dumps(stage103))
            (work/'stage104_prewarm_diff_private.json').write_text(json.dumps(stage104))
            stub=type('Stage102Stub',(),{'authentic_wavs':staticmethod(lambda _: (b'',b'')),
                'wav_first_n_vendor_samples':staticmethod(lambda _, __: y)})
            with (mock.patch.object(m,'PRIVATE_ROOT',root),
                  mock.patch.object(m,'FRAMES',N),
                  mock.patch.object(m,'FIT_START',20),
                  mock.patch.object(m,'FIT_END',140),
                  mock.patch.object(m,'COARSE',20),
                  mock.patch.object(m,'FINE',10),
                  mock.patch.object(m,'MAX_LAG',2),
                  mock.patch.object(m,'load_module',return_value=stub)):
                result=m.run(work/'comparison_private.json',root/'not-a-vendor-file.zip')
                self.assertEqual(result['status'],'STAGE105_OFFLINE_GAIN_ENERGY_LAG_TOPOLOGY_COMPLETED')
                self.assertEqual(len(result['coarse_200k_summary']),6)
                self.assertEqual(len(json.loads((work/'stage105_error_topology_private.json').read_text())['fine_20k']),12)
                with self.assertRaisesRegex(ValueError,'refusing to overwrite'):
                    m.run(work/'comparison_private.json',root/'not-a-vendor-file.zip')

    def test_original_bytes_sha_guard(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'private.f64le'
            f.write_bytes(b'12345678')
            with self.assertRaisesRegex(ValueError,'SHA or size'):
                m.read_f64_checked(f,m.sha(f))

if __name__=='__main__':unittest.main()
