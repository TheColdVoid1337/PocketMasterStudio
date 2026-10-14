"""Stage62 strict, deterministic *offline* source-patch tests."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"stages"/"stage62"/"audit_native_window.py"
spec=importlib.util.spec_from_file_location("_htkpa62_test",SCRIPT)
assert spec is not None and spec.loader is not None
audit=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=audit
spec.loader.exec_module(audit)


def mock_upstream():
    return ("static const double Coeffs2[][3] = {"
            "{ 9.5945017884101773, 1.9718456992078597, 182.1076 },"
            "};\n"
            "void constructor(){\n"
            "    const double* const Params = getWinParams( ReqAtten, IsThird,\n"
            "        FilterLen );\n"
            "}\n")


class Stage62Tests(unittest.TestCase):
    def test_native_constants_are_exact_original_ieee754(self):
        self.assertEqual(audit.NATIVE_BETA.hex(),"0x1.91af20df9e8bap+3")
        self.assertEqual(audit.NATIVE_POWER.hex(),"0x1.83fa5ca7f6a99p+0")
        self.assertEqual(audit.NATIVE_BETA,12.55262798)
        self.assertEqual(audit.NATIVE_POWER,1.51553897)
        self.assertEqual(audit.PUBLIC_BETA,9.5945017884101773)
        self.assertEqual(audit.PUBLIC_POWER,1.9718456992078597)
        self.assertTrue((audit.HERE.parent/"stage59"/"public_frac_bank.cpp").is_file())

    def test_exact_three_window_hypotheses(self):
        pairs={
            "native_beta_only":(audit.NATIVE_BETA,audit.PUBLIC_POWER),
            "native_power_only":(audit.PUBLIC_BETA,audit.NATIVE_POWER),
            "native_both":(audit.NATIVE_BETA,audit.NATIVE_POWER),
        }
        self.assertEqual(set(audit.TRIALS),set(pairs))
        for trial,(b,p) in pairs.items():
            with self.subTest(trial=trial):
                changed,details=audit.patch_public_header(mock_upstream(),trial)
                self.assertEqual((details["beta"],details["power"]),(b,p))
                self.assertEqual(changed.count("HTKPA_Stage62_Params"),2)
                self.assertEqual(changed.count("FilterLen = 24;"),1)
                self.assertNotIn("= getWinParams( ReqAtten",changed)
                self.assertIn(b.hex(),changed)
                self.assertIn(p.hex(),changed)

    def test_crlf_source_normalized_and_unknown_layout_rejected(self):
        changed,_=audit.patch_public_header(mock_upstream().replace("\n","\r\n"),
                                               "native_both")
        self.assertNotIn("\r\n",changed)
        with self.assertRaises(ValueError):
            audit.patch_public_header(mock_upstream(),"unknown")
        with self.assertRaises(ValueError):
            audit.patch_public_header(mock_upstream().replace(
                audit.PUBLIC_ROW_GUARD,"not actual source"),"native_both")
        with self.assertRaises(ValueError):
            audit.patch_public_header(mock_upstream()+
                " const double* const Params = getWinParams( ReqAtten, IsThird,"
                "FilterLen );","native_both")

    def test_analytic_kernel_unit_dc_at_integer_phase(self):
        import numpy as np
        b=audit.analytic_c0(audit.NATIVE_BETA,audit.NATIVE_POWER)
        self.assertEqual(b.shape,(673,24))
        self.assertLess(float(np.max(np.abs(b.sum(axis=1)-1.0))),1e-12)
        self.assertAlmostEqual(float(b[0,11]),1.0,places=13)
        self.assertLess(float(np.max(np.abs(b[0,np.arange(24)!=11]))),1e-12)
        self.assertAlmostEqual(float(b[336,11]),0.6275702,places=6)

    def test_analytic_kernel_rejects_bad_parameters(self):
        for beta,power in ((0,1),(-1,1),(3,-2),(float("nan"),1)):
            with self.assertRaises(ValueError):
                audit.analytic_c0(beta,power)

    def test_numeric_score_identity_contract(self):
        import struct
        sample=struct.pack("<d",1.0)+b"\0"*(48456*8-8)
        m=audit.summarize_metric(sample,sample)
        self.assertEqual(m["bit_equal"],48456)
        self.assertEqual(m["rms_error"],0)
        self.assertIsNone(m["rms_improvement_vs_public"])
        self.assertEqual(m["phase_336_rms"],0)


if __name__=="__main__":
    unittest.main()
