"""Stage55 offline-only unit checks (stdlib; no native data, no r8brain source required)."""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT/"research"/"htkpa"/"stages"/"stage55"/"audit_numeric.py"
spec = importlib.util.spec_from_file_location("htkpa_stage55_audit", MODULE)
assert spec and spec.loader
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


class Stage55OfflineTests(unittest.TestCase):
    def test_repository_and_source_path_contract(self):
        self.assertEqual(audit.ROOT, ROOT)
        self.assertEqual(set(audit.PINS), {"v6.5", "v7.2"})
        self.assertTrue((audit.HERE/"public_reverse.cpp").is_file())
        self.assertTrue((audit.HERE.parent/"stage44"/"public_resampler.cpp").is_file())
        self.assertEqual(audit.EXPECTED["stage54_tar"],
                         "d2275640d357bca7b03ed413c464037eb07f8abb1a4a6d75a2b54ced8b8181a8")

    def test_bitexact_and_subulp_float_compare(self):
        n = struct.pack("<32d", *(float(i + 1) for i in range(32)))
        m = audit.metric(n, n + b"\x00"*8)
        self.assertEqual(m["status"], "COMPARED_SAME_INDEX_FIRST_32")
        self.assertEqual(m["bit_equal"], 32)
        self.assertEqual(m["max_abs_error"], 0.0)
        self.assertEqual(m["rms_error"], 0.0)
        altered = bytearray(n)
        altered[:8] = struct.pack("<d", math.nextafter(1.0, 2.0))
        result = audit.metric(n, bytes(altered))
        self.assertEqual(result["bit_equal"],31)
        self.assertGreater(result["max_abs_error"],0)
        self.assertEqual(result["native_first32_sha256"],audit.sha(n))

    def test_never_search_for_arbitrary_shift(self):
        native=struct.pack("<32d",*(float(x) for x in range(32)))
        public=struct.pack("<33d",99.,*(float(x) for x in range(32)))
        m=audit.metric(native,public)
        self.assertEqual(m["status"],"COMPARED_SAME_INDEX_FIRST_32")
        self.assertEqual(m["bit_equal"],0)
        self.assertNotEqual(m["max_abs_error"],0)
        self.assertEqual(audit.metric(native,public[:8])["status"],"UNALIGNED_OR_TOO_SHORT")

    def test_nonfinite_comparison_refused(self):
        bad=struct.pack("<32d",float("nan"),*([0.] * 31))
        with self.assertRaises(ValueError):
            audit.metric(bad,struct.pack("<32d",*([0.] * 32)))

    def test_fixed_input_pins_and_geometry(self):
        self.assertEqual(audit.EXPECTED["native_96k_first3"],
            "df36dcda32dbed569581efe826190733e83d41cff2f48850ace5f033c98470d6")
        self.assertEqual(audit.EXPECTED["native_96k_next256"],
            "9136f8dd141fac2efa13e1addcac2e7fc004a52140fa57498fe3c88ff325471c")
        self.assertEqual(audit.EXPECTED["native_48k_first32"],
            "6221729cf455706ac4b5ab9bedbada953836089ae2399d10fc6c87de3f4a1782")
        self.assertEqual(audit.EXPECTED["native_44k_first32"],
            "65b48ee4d3a6b0f86f8ab539761f45d52fc5799a7ce8a4e88b86c215eb0b6dae")


if __name__ == "__main__":
    unittest.main()
