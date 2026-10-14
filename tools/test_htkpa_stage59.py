"""Stage59 offline-only metrics tests (does not contact Git or load native app)."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
FILE=HERE/"research"/"htkpa"/"stages"/"stage59"/"audit_coeff.py"
spec=importlib.util.spec_from_file_location("_htkpa_stage59_test",FILE)
assert spec and spec.loader
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)

class Stage59Tests(unittest.TestCase):
    def test_exact_geometry_and_pins(self):
        self.assertEqual(m.N,673*72)
        self.assertEqual(m.BYTES,387648)
        self.assertTrue((FILE.parent/"public_frac_bank.cpp").is_file())
        self.assertEqual(len(m.PINS),2)
        self.assertEqual(m.DLL_SHA,
            "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")

    def test_zero_error_is_entire_bank_bit_equal(self):
        raw=struct.pack("<d",1.0)+b"\x00"*(m.BYTES-8)
        res=m.metrics(raw,raw)
        self.assertEqual(res["f64"],m.N)
        self.assertEqual(res["bit_equal"],m.N)
        self.assertEqual(res["max_abs_error"],0)
        self.assertEqual(res["rms_error"],0)

    def test_different_coefficient_detected_without_shift(self):
        raw=struct.pack("<d",1.0)+b"\x00"*(m.BYTES-8)
        other=struct.pack("<d",2.0)+raw[8:]
        res=m.metrics(raw,other)
        self.assertEqual(res["bit_equal"],m.N-1)
        self.assertGreater(res["max_abs_error"],0)
        self.assertGreater(res["row_rms_p0"],0)
        self.assertEqual(res["row_rms_p336"],0)

    def test_corrupt_length_is_not_scored(self):
        with self.assertRaises(ValueError):
            m.metrics(b"\x00"*8,b"\x00"*8)


if __name__=="__main__":
    unittest.main()
