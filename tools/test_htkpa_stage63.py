"""Stage63 offline source patch and provenance checks; no native app invocation."""
from __future__ import annotations
import importlib.util
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"research"/"htkpa"/"stages"/"stage63"/"audit_audio_parity.py"
spec=importlib.util.spec_from_file_location("_htkpa_test_stage63",SCRIPT)
assert spec is not None and spec.loader is not None
audit=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=audit
spec.loader.exec_module(audit)


def mock_upstream():
    # Exact two pinned anchors from pristine public CDSPFracInterpolator.h.
    return (
        "static const double Coeffs2[12][3] = {\n"
        " {9.5945017884101773, 1.9718456992078597, 182.1076}\n"
        "};\n"
        "void make_bank() {\n"
        "  const double* const Params = getWinParams( ReqAtten, IsThird,\n"
        "      FilterLen );\n"
        "  FilterFracs = (int) ceil( pow( 6.4, ReqAtten / 50.0 ));\n"
        "}\n"
        "void setup() {\n"
        "IsWhole = getWholeStepping( SrcSampleRate, DstSampleRate, InStep,\n"
        "\t\t\tOutStep );\n"
        "}\n"
    )


class Stage63OfflineTests(unittest.TestCase):
    def test_public_pins_and_exact_three_trials(self):
        self.assertEqual(audit.stage55.PINS[audit.VERSION],
                         "3c930bf6825c0cfea4a813210c83b1a650c820b5")
        self.assertEqual(audit.TRIALS,
            ("native_window_whole","native_window_poly_default","native_window_poly_673"))
        self.assertEqual(audit.REVERSE_NATIVE_LENGTHS,[0,114])
        self.assertEqual(audit.FORWARD_NATIVE_LENGTH,1067)
        self.assertTrue((audit.HERE.parent/"stage55"/"public_reverse.cpp").exists())
        self.assertTrue((audit.HERE.parent/"stage44"/"public_resampler.cpp").exists())

    def test_window_only_retains_original_ratio_step_code(self):
        original=mock_upstream()
        patched,info=audit.patch_header(original,"native_window_whole")
        self.assertIn(audit.stage57.WHOLE_STEPPING,patched)
        self.assertIn(audit.stage57.FRAC_COUNT,patched)
        self.assertIn(audit.stage62.NATIVE_BETA.hex(),patched)
        self.assertIn(audit.stage62.NATIVE_POWER.hex(),patched)
        self.assertEqual(info["interpolation_mode"],"upstream_whole_or_auto")

    def test_combined_native_window_and_poly_673_exact_patch(self):
        original=mock_upstream()
        patched,info=audit.patch_header(original,"native_window_poly_673")
        self.assertNotIn(audit.stage57.WHOLE_STEPPING,patched)
        self.assertNotIn(audit.stage57.FRAC_COUNT,patched)
        self.assertIn("FilterFracs = 673;",patched)
        self.assertIn("IsWhole = false;",patched)
        self.assertIn("FilterLen = 24;",patched)
        self.assertIn(audit.stage62.NATIVE_BETA.hex(),patched)
        self.assertIn(audit.stage62.NATIVE_POWER.hex(),patched)
        self.assertEqual(info["phase_positions"],673)
        self.assertTrue(info["only_private_public_source_patched"])

    def test_poly_default_does_not_force_phase_positions(self):
        patched,info=audit.patch_header(mock_upstream(),"native_window_poly_default")
        self.assertIn(audit.stage57.FRAC_COUNT,patched)
        self.assertIn("IsWhole = false;",patched)
        self.assertIsNone(info["phase_positions"])

    def test_unsupported_variant_and_mutated_upstream_fail_closed(self):
        with self.assertRaises(ValueError):
            audit.patch_header(mock_upstream(),"unexpected")
        with self.assertRaises(ValueError):
            audit.patch_header(mock_upstream().replace(
                "9.5945017884101773","0.0"),"native_window_poly_673")
        with self.assertRaises(ValueError):
            audit.patch_header(mock_upstream().replace(
                audit.stage57.FRAC_COUNT,"FilterFracs = 999;"),
                "native_window_poly_673")

    def test_metric_exact_and_deliberately_shifted_prefix(self):
        n=struct.pack("<32d",*(float(i+1) for i in range(32)))
        m=audit.sample_error(n,n)
        self.assertEqual(m["bit_equal"],32)
        self.assertEqual(m["rms_error"],0.0)
        self.assertEqual(m["sample_indices_max_abs"],list(range(32)))
        different=struct.pack("<32d",*(float(i+2) for i in range(32)))
        other=audit.sample_error(n,different)
        self.assertEqual(other["bit_equal"],0)
        self.assertEqual(other["max_abs_error"],1.0)
        self.assertGreater(other["rms_to_native_rms"],0.0)

    def test_stage62_archive_validation_checks_verified_numeric_gate(self):
        with tempfile.TemporaryDirectory() as d:
            where=Path(d)/"run.tar.gz"
            sample={
                "status":"NATIVE_WINDOW_PARAMS_HYPOTHESES_MEASURED",
                "source_commit":audit.stage55.PINS[audit.VERSION],
                "native":{"coefficient_sha256":audit.stage62.NATIVE_SHA},
                "results":{"native_both":{"window":{
                    "beta_f64_hex":audit.stage62.NATIVE_BETA.hex(),
                    "power_f64_hex":audit.stage62.NATIVE_POWER.hex()},
                    "metrics":{"bank_sha256":audit.STAGE62_COEFF_PUBLIC_SHA,
                               "rms_error":audit.STAGE62_NUMERIC_RMS,
                               "bit_equal":4722}}}}
            with tarfile.open(where,"w:gz") as t:
                for name,content in (
                    ("run.json",json.dumps({"status":"SUCCEEDED"}).encode()),
                    ("output/stage62_native_window.json",json.dumps(sample).encode())):
                    data=io.BytesIO(content)
                    info=tarfile.TarInfo(name)
                    info.size=len(content)
                    t.addfile(info,data)
            with mock.patch.object(audit,"STAGE62_TAR_SHA",
                                   audit.stage55.sha(where.read_bytes())):
                report=audit.check_stage62(where)
                self.assertEqual(report["bank_bit_equal"],4722)
                sample["results"]["native_both"]["metrics"]["rms_error"]=1e-4
                with tarfile.open(where,"w:gz") as t:
                    for name,content in (
                        ("run.json",json.dumps({"status":"SUCCEEDED"}).encode()),
                        ("output/stage62_native_window.json",json.dumps(sample).encode())):
                        data=io.BytesIO(content)
                        info=tarfile.TarInfo(name)
                        info.size=len(content)
                        t.addfile(info,data)
                with mock.patch.object(audit,"STAGE62_TAR_SHA",
                                       audit.stage55.sha(where.read_bytes())):
                    with self.assertRaises(ValueError):
                        audit.check_stage62(where)


if __name__=="__main__":
    unittest.main()
