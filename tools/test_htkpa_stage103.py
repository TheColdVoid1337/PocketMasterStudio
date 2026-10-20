"""Stage103 offline zero-lag gain/residual arithmetic fixtures; no vendor files."""
import importlib.util
from pathlib import Path
import math
import unittest

S=Path(__file__).resolve().parents[1]/'research/htkpa/stages/stage103/GO.py'
p=importlib.util.spec_from_file_location('stage103_go',S)
m=importlib.util.module_from_spec(p);p.loader.exec_module(m)

class TestStage103(unittest.TestCase):
    def test_gain_proportional(self):
        x=[0.1,0.2,-0.3,0.1]
        y=[v*0.25 for v in x]
        r=m.segment_metrics(y,x,0,4)
        self.assertAlmostEqual(r['gain_open_to_manager_least_squares'],0.25)
        self.assertLess(r['rms_after_gain_only'],1.e-8)
        self.assertAlmostEqual(r['zero_lag_cosine_similarity'],1)
        self.assertFalse(r['lag_fitted'])

    def test_window_slice(self):
        y=[1,2,3,4,5,6]
        x=[1,2,3,4,5,6]
        a=m.segment_metrics(y,x,1,3)
        self.assertEqual((a['start'],a['stop_exclusive'],a['frames']),(1,3,2))
        self.assertAlmostEqual(a['gain_open_to_manager_least_squares'],1)

    def test_known_wrong_sign(self):
        r=m.segment_metrics([1,-2],[2,-4],0,2)
        self.assertAlmostEqual(r['gain_open_to_manager_least_squares'],0.5)
        r=m.segment_metrics([1,-2],[-2,4],0,2)
        self.assertAlmostEqual(r['gain_open_to_manager_least_squares'],-0.5)

    def test_orthogonal_error(self):
        r=m.segment_metrics([1,0],[0,1],0,2)
        self.assertEqual(r['gain_open_to_manager_least_squares'],0.0)
        self.assertAlmostEqual(r['normalized_rms_after_gain_only'],1)

    def test_reject_nonfinite(self):
        with self.assertRaisesRegex(ValueError,'non-finite'):
            m.segment_metrics([1,float('nan')],[1,2],0,2)

    def test_reject_silence(self):
        with self.assertRaisesRegex(ValueError,'silence'):
            m.segment_metrics([0,0],[1,1],0,2)

    def test_reject_ranges(self):
        for a,b in ((0,0),(-1,1),(0,7),(2,1)):
            with self.assertRaises(ValueError):m.segment_metrics([1,2],[1,2],a,b)

    def test_analysis_requires_full_frames(self):
        with self.assertRaisesRegex(ValueError,'1,600,000'):
            m.evaluate([1],[1])

    def test_boundaries(self):
        self.assertEqual(m.FIT_START,300000)
        self.assertEqual(m.FIT_END,1500000)
        self.assertEqual(m.FRAMES,1600000)

if __name__=='__main__':unittest.main()
