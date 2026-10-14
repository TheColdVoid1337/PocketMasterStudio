"""Stage60 numerical projections, offline only (synthetic coefficient banks)."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"stages"/"stage60"/"audit_residual.py"
spec=importlib.util.spec_from_file_location("_htkpa_stage60_test",SCRIPT)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


def synthetic()->np.ndarray:
    x=np.arange(673,dtype=np.float64)[:,None,None]
    t=np.arange(24,dtype=np.float64)[None,:,None]
    c=np.arange(3,dtype=np.float64)[None,None,:]
    return (np.sin(x*0.008+t*0.25+c*0.37)+0.1*np.cos(x*0.013-t*0.21+c))


class Stage60OfflineTests(unittest.TestCase):
    def test_shape_and_shas_are_pinned(self):
        self.assertEqual((m.NPHASES,m.NTAPS,m.NCOEFFS),(673,24,3))
        self.assertEqual(m.EXPECTED_NATIVE_SHA,
            "14acac11db2295b56e7bc2693b8e9b34368e5b455be2911425bc6825fe81a601")
        self.assertEqual(m.EXPECTED_PUBLIC_SHA,
            "dbe44bde762d9d7b7259671e52b335f5def2d8d247996b4c43c8a2fb3319e24b")
        self.assertTrue((ROOT/"research"/"htkpa"/"stages"/"stage59"/"public_frac_bank.cpp").is_file())

    def test_identical_banks_have_zero_error(self):
        public=synthetic()
        report=m.phase_profile(public,public)
        self.assertTrue(all(v["rms"]==0 for v in report["by_coeff"]))
        self.assertTrue(all(v["rms"]==0 for v in report["selected_phases"]))
        analysis=m.project_phase_model(public,public)
        self.assertEqual(analysis["original"]["rms"],0.0)
        self.assertEqual(analysis["gain_fit"]["gain"],1.0)
        self.assertEqual(analysis["phase_offset_uniform"]["bounded_delta_positions"],0.0)

    def test_global_gain_fit_identifies_synthetic_gain(self):
        public=synthetic()
        native=public*1.001
        result=m.project_phase_model(native,public)
        self.assertAlmostEqual(result["gain_fit"]["gain"],1.001,places=12)
        self.assertLess(result["gain_fit"]["rms"],1e-12)

    def test_phase_bulge_projection_recovers_known_small_shift(self):
        public=synthetic()
        derivative=(public[2:]-public[:-2])*0.5
        x=np.arange(1,672,dtype=float)/672
        bulge=4*x*(1-x)
        native=public.copy()
        native[1:-1]+=0.2*derivative*bulge[:,None,None]
        result=m.project_phase_model(native,public)
        fitted=result["phase_offset_zero_at_edges_bulge"]
        self.assertAlmostEqual(fitted["unconstrained_delta_positions"],0.2,places=10)
        self.assertTrue(fitted["within_half_phase"])
        self.assertLess(fitted["projected_interior_rms"],1e-13)
        self.assertGreater(fitted["improvement_factor"],100)

    def test_projection_is_explicitly_bounded(self):
        public=synthetic()
        native=public.copy()
        derivative=(public[2:]-public[:-2])*0.5
        native[1:-1]+=5*derivative
        result=m.project_phase_model(native,public)
        constant=result["phase_offset_uniform"]
        self.assertFalse(constant["within_half_phase"])
        self.assertEqual(constant["bounded_delta_positions"],0.5)

    def test_nonfinite_values_rejected(self):
        public=synthetic()
        bad=public.copy()
        bad[0,0,0]=float("nan")
        with self.assertRaises(ValueError):
            m.phase_profile(bad,public)
        with self.assertRaises(ValueError):
            m.project_phase_model(public,bad)


if __name__=="__main__":
    unittest.main()
