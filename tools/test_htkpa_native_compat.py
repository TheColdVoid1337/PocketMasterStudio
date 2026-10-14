"""Stage66 standalone C ABI regression gates (no private archives / source checkout).

The full C++ compilation and vendor numerical test run only via
research/htkpa/native_compat/audit_bridge.py with an explicit pinned source
cache and Stage49/54/62/63/64 evidence. No network or vendor DLL access.
"""
from __future__ import annotations
import importlib.util
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"native_compat"/"audit_bridge.py"
spec=importlib.util.spec_from_file_location("_htkpa_stage66_test",SCRIPT)
assert spec is not None and spec.loader is not None
m=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=m
spec.loader.exec_module(m)


class Stage66Tests(unittest.TestCase):
    def test_standalone_bridge_build_contract_and_provenance(self):
        bridge=(SCRIPT.parent/"htkpa_native_frac_bridge.cpp")
        self.assertTrue(bridge.is_file())
        text=bridge.read_text(encoding="utf-8")
        for token in ("htkpa_v1_open(", "htkpa_v1_process(",
                      "htkpa_v1_reset(", "htkpa_v1_close(",
                      "htkpa_v1_min_output_capacity(",
                      "CDSPFracInterpolator(", "CDSPResampler(",
                      "std::memcpy", "std::isfinite"):
            self.assertIn(token,text)
        self.assertNotIn("LoadLibrary(",text)
        self.assertEqual(m.API_ID,
            "r8brain-v6.5__sonicake-1.5.2__kaiser12.55262798_1.51553897__poly673")
        self.assertEqual(m.EXPECTED_NATIVE_COUNTS,{"reverse":114,"forward":1067})
        self.assertEqual(m.PIN,"v6.5")
        self.assertEqual(len(m.EXPECTED_PATCHED_FULL_SHA),2)

    def test_decode_and_metric_on_exact_original_extended_geometry(self):
        for count in (114,1067):
            packed=struct.pack("<"+str(count)+"d",*(0.1+0.001*i for i in range(count)))
            values=m.decode_f64(packed)
            self.assertEqual(len(values),count)
            self.assertEqual(m.metric(packed,packed,count)["bit_equal"],count)
            self.assertEqual(m.metric(packed,packed,count)["rms_error"],0)
            with self.assertRaises(ValueError):
                m.decode_f64(packed+b"\x00")

    def test_compatible_sample_splits_replay_and_reset(self):
        class FakeStream:
            def __init__(self,library,mode):
                self.mode=mode
                self.position=0
                self.is_closed=False
            def process(self,values):
                # A fake deterministic stateful implementation: split samples
                # must have equal total output regardless of call boundaries.
                data=struct.pack("<"+str(len(values))+"d",*(
                    value+(i+self.position)*0.125 for i,value in enumerate(values)))
                self.position+=len(values)
                return data
            def reset(self):
                self.position=0
            def close(self):
                self.is_closed=True
        nums=[float(i) for i in range(22)]
        with patch.object(m,"Stream",FakeStream):
            one=m.run_blocks(None,m.MODE_REVERSE,[nums])
            split=m.run_blocks(None,m.MODE_REVERSE,[nums[:3],nums[3:]])
        self.assertEqual(one,split)

    def test_failure_of_reset_replay_is_detected(self):
        class FakeBadStream:
            def __init__(self,lib,mode):
                self.calls=0
            def process(self,vals):
                self.calls+=1
                return struct.pack("<d",float(self.calls))
            def reset(self):
                pass
            def close(self):
                pass
        with patch.object(m,"Stream",FakeBadStream):
            with self.assertRaisesRegex(ValueError,"reset"):
                m.run_blocks(None,1,[[1.0]])

    def test_exact_source_patch_cannot_silently_use_default_whole_mode(self):
        before=("IsWhole = getWholeStepping( SrcSampleRate, DstSampleRate, InStep,\n"
                "\t\t\tOutStep );")
        self.assertEqual(m.stage63.stage57.WHOLE_STEPPING,before)
        self.assertIn("FilterFracs = 673;",
                      m.stage63.stage57.patch_frac_header(
                          "FilterFracs = (int) ceil( pow( 6.4, ReqAtten / 50.0 ));\n"
                          +before, "poly_673")[0])
        self.assertEqual(m.stage63.stage62.NATIVE_BETA,12.55262798)
        self.assertEqual(m.stage63.stage62.NATIVE_POWER,1.51553897)


if __name__=="__main__":
    unittest.main()
