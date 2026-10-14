"""Stage61 offline regression gates. Never reads user's private bank or vendor DLL."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"stages"/"stage61"/"audit_bank_params.py"
spec=importlib.util.spec_from_file_location("_htkpa_stage61_test",SCRIPT)
assert spec is not None and spec.loader is not None
audit=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=audit
spec.loader.exec_module(audit)


class Stage61Tests(unittest.TestCase):
    def test_fixed_grid_has_baseline_and_two_filter_families(self):
        grid=audit.candidates()
        self.assertEqual(len(grid),86)
        self.assertEqual(len(set(grid)),86)
        self.assertIn((180.15,0),grid)
        self.assertIn((182.1076,0),grid)
        self.assertIn((180.15,1),grid)
        self.assertEqual({b for a,b in grid},{0,1})
        self.assertTrue(all(170<=a<=190 for a,b in grid))

    def test_source_identity_guard(self):
        self.assertTrue((audit.HERE/"public_bank_variant.cpp").is_file())
        self.assertEqual(audit.base.PINS[audit.PIN],
                         "3c930bf6825c0cfea4a813210c83b1a650c820b5")
        self.assertEqual(audit.NATIVE_EXPECTED,
                         "14acac11db2295b56e7bc2693b8e9b34368e5b455be2911425bc6825fe81a601")
        self.assertEqual(audit.PUBLIC_EXPECTED,
                         "dbe44bde762d9d7b7259671e52b335f5def2d8d247996b4c43c8a2fb3319e24b")

    def test_identity_and_one_perturbation_score(self):
        arr=np.zeros(audit.base.N,dtype="<f8")
        arr[0]=1.0
        raw=arr.tobytes()
        reference=audit.candidate_score(raw,raw)
        self.assertEqual(reference["bit_equal"],audit.base.N)
        self.assertEqual(reference["rms_error"],0)
        self.assertEqual(reference["component_rms"],[0.0,0.0,0.0])
        self.assertIsNone(reference["rms_vs_stage59_factor"])
        changed=arr.copy()
        changed[0]+=1e-4
        comparison=audit.candidate_score(raw,changed.tobytes())
        self.assertEqual(comparison["bit_equal"],audit.base.N-1)
        self.assertGreater(comparison["rms_error"],0)
        self.assertGreater(comparison["component_rms"][0],0)
        self.assertEqual(comparison["component_rms"][1],0)
        self.assertEqual(comparison["component_rms"][2],0)

    def test_rank_by_actual_coefficient_error_not_requested_attenuation(self):
        first={"requested_attenuation":180.15,
               "metrics":{"rms_error":1e-4,"max_abs_error":2e-4,"bit_equal":2}}
        second={"requested_attenuation":178.0,
                "metrics":{"rms_error":1e-7,"max_abs_error":2e-7,"bit_equal":0}}
        self.assertLess(audit.row_rank(second),audit.row_rank(first))

    def test_geometry_mismatch_is_not_scored(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as d:
            dest=Path(d)/"untouched.f64le"
            response=SimpleNamespace(returncode=0,
                stdout='{"geometry_ok":false,"taps":22,"phases":673}\n',
                stderr="")
            with patch.object(audit.subprocess,"run",return_value=response):
                metadata,samples=audit.run_one(Path(d)/"fake_public",dest,180.15,0)
            self.assertEqual(metadata["taps"],22)
            self.assertIsNone(samples)
            self.assertFalse(dest.exists())


if __name__=="__main__":
    unittest.main()
