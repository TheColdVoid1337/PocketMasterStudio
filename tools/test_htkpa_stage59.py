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

    def test_simd_pair_pack_unpack_roundtrip_48456_coefficients(self):
        import numpy as np
        scalar=np.arange(m.N,dtype="<f8").reshape(673,12,6)
        packed=scalar[:,:,(0,3,1,4,2,5)].copy().tobytes()
        restored=m.convert_public_layout(packed,"simd_pairs_2tap")
        self.assertEqual(restored,scalar.tobytes())
        self.assertEqual(m.metrics(scalar.tobytes(),restored)["bit_equal"],m.N)
        self.assertGreater(m.metrics(scalar.tobytes(),packed)["max_abs_error"],0)

    def test_stage59_layout_decoding_refuses_unknown_layout_or_wrong_size(self):
        import numpy as np
        raw=np.arange(m.N,dtype="<f8").tobytes()
        self.assertEqual(m.convert_public_layout(raw,"scalar_triplets"),raw)
        with self.assertRaises(ValueError):
            m.convert_public_layout(raw,"unspecified")
        with self.assertRaises(ValueError):
            m.convert_public_layout(raw[:-8],"simd_pairs_2tap")

    def test_simd_layout_permutation_matches_known_vector_example(self):
        import numpy as np
        sample=np.zeros((673,12,6),dtype="<f8")
        sample[0,0,:]=[10,20,30,40,50,60]
        packed=sample[:,:,(0,3,1,4,2,5)].copy().tobytes()
        self.assertEqual(np.frombuffer(packed,dtype="<f8")[:6].tolist(),
                         [10,40,20,50,30,60])
        unpacked=m.convert_public_layout(packed,"simd_pairs_2tap")
        self.assertEqual(np.frombuffer(unpacked,dtype="<f8")[:6].tolist(),
                         [10,20,30,40,50,60])

    def test_corrupt_length_is_not_scored(self):
        with self.assertRaises(ValueError):
            m.metrics(b"\x00"*8,b"\x00"*8)


if __name__=="__main__":
    unittest.main()
