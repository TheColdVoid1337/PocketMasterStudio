"""Stage56 pure offline tests: no native audio, Windows process or public build."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"research"/"htkpa"/"stages"/"stage56"/"audit_hypotheses.py"
spec=importlib.util.spec_from_file_location("htkpa_stage56_audit",SOURCE)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class Stage56Tests(unittest.TestCase):
    def test_public_contract_and_pins(self):
        self.assertTrue((m.HERE/"public_forward_variant.cpp").is_file())
        self.assertTrue((m.HERE.parent/"stage55"/"public_reverse.cpp").is_file())
        self.assertEqual(m.old.PINS["v6.5"],
                         "3c930bf6825c0cfea4a813210c83b1a650c820b5")
        self.assertEqual(m.EXPECTED_REVERSE_COUNTS,[0,114])
        self.assertEqual(m.EXPECTED_FORWARD_COUNT,1067)
        self.assertIn(180.15,m.R_ATTENUATIONS)
        self.assertIn(180.15,m.F_ATTENUATIONS)
        self.assertIn(2.0,m.F_TRANSBANDS)
        self.assertIn(0.0,m.R_LATENCIES)

    def test_geometry_mismatch_cannot_be_ranked_best(self):
        ok={"metric":{"status":"COMPARED_SAME_INDEX_FIRST_32",
                      "rms_error":0.01,"max_abs_error":0.02,"bit_equal":1}}
        nope={"metric":{"status":"GEOMETRY_MISMATCH","counts":[0,116]}}
        self.assertLess(m.rank_key(ok),m.rank_key(nope))
        grouped=m.summary([nope,ok])
        self.assertEqual(grouped["matching_output_geometry"],1)
        self.assertEqual(grouped["top"][0],ok)

    def test_improvement_means_lower_rms_not_more_exact_accidentally(self):
        a={"metric":{"status":"COMPARED_SAME_INDEX_FIRST_32",
                     "rms_error":1e-4,"max_abs_error":4e-4,"bit_equal":30}}
        b={"metric":{"status":"COMPARED_SAME_INDEX_FIRST_32",
                     "rms_error":1e-8,"max_abs_error":4e-8,"bit_equal":0}}
        self.assertLess(m.rank_key(b),m.rank_key(a))
        self.assertEqual(m.summary([a,b])["top"][0],b)

    def test_bounded_candidate_grid(self):
        self.assertLessEqual(len(m.R_ATTENUATIONS)*4,60)
        self.assertLessEqual(len(m.F_TRANSBANDS)*len(m.F_ATTENUATIONS),32)
        self.assertTrue(all(math.isfinite(x) for x in
                            (*m.R_ATTENUATIONS,*m.F_ATTENUATIONS,
                             *m.F_TRANSBANDS,*m.R_LATENCIES)))


if __name__=="__main__":
    unittest.main()
