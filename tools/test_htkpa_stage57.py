"""Stage57 source-translation regressions. No GitHub Actions/native DLL execution."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import sys
import unittest

PROJECT=Path(__file__).resolve().parents[1]
PATH=PROJECT/"research"/"htkpa"/"stages"/"stage57"/"audit_poly.py"
spec=importlib.util.spec_from_file_location("_htkpa_test_stage57",PATH)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class Stage57OfflineTests(unittest.TestCase):
    def setUp(self):
        self.upstream=(
            "if( InitFilterFracs == -1 ) {\n" + m.FRAC_COUNT + "\n}\n"
            "void construct() {\n" + m.WHOLE_STEPPING + "\n}\n")

    def test_poly_default_leaves_native_fraction_formula_intact(self):
        text,info=m.patch_frac_header(self.upstream,"poly_default_fracs")
        self.assertIn(m.FRAC_COUNT,text)
        self.assertNotIn(m.WHOLE_STEPPING,text)
        self.assertEqual(text.count("IsWhole = false;"),1)
        self.assertIsNone(info["forced_filter_fracs"])

    def test_poly673_uses_fixed_native_phase_count(self):
        text,info=m.patch_frac_header(self.upstream,"poly_673")
        self.assertNotIn(m.FRAC_COUNT,text)
        self.assertIn("FilterFracs = 673;",text)
        self.assertEqual(info["native_assembly_taps"],24)
        self.assertEqual(info["native_interp_element_size"],3)
        self.assertEqual(info["forced_filter_fracs"],673)

    def test_unexpected_or_ambiguous_public_header_refused(self):
        for source in (self.upstream+"\n"+m.WHOLE_STEPPING,
                       self.upstream+"\n"+m.FRAC_COUNT,
                       self.upstream.replace("IsWhole = getWholeStepping","IsWhole = other"),
                       self.upstream.replace("6.4","6.5")):
            with self.assertRaises(ValueError):
                m.patch_frac_header(source,"poly_673")
        with self.assertRaises(ValueError):
            m.patch_frac_header(self.upstream,"unknown")

    def test_crlf_header_is_handled_without_relaxing_exact_match(self):
        text,_=m.patch_frac_header(self.upstream.replace("\n","\r\n"),"poly_673")
        self.assertIn("FilterFracs = 673;",text)
        self.assertNotIn("\r\n",text)

    def test_counts_guard_and_no_comparison_on_geometry_mismatch(self):
        native=b"\x00"*256
        self.assertEqual(m.row_metric(native,b"",False)["status"],
                         "GEOMETRY_MISMATCH_NOT_COMPARABLE")
        self.assertEqual(m.row_metric(native,native,True)["bit_equal"],32)
        self.assertIsNone(m.factor(1.0,{}))
        self.assertIsNone(m.factor(1.0,{"rms_error":0}))


if __name__=="__main__":
    unittest.main()
