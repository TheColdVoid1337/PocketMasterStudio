"""Stage80 tests: synthetic cases; no original DLL, model or Frida execution."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage80/audit_nam_capture_identity.py"
spec = importlib.util.spec_from_file_location("stage80_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def nam(architecture="SlimmableContainer", rate=48000, version="0.7.0") -> bytes:
    return json.dumps({"architecture": architecture, "sample_rate": rate,
                       "version": version, "config": {"submodels": []},
                       "weights": {"synthetic": [0.1]}}).encode()


def accepted_stage79() -> dict:
    return {"status": mod.stage79.STATUS_NO_KEY,
            "stage64_metadata_inspection": {"candidate_count": 0},
            "claims": {"stage64_input_model_architecture_proven": False,
                       "specific_stage64_factory_selected": False}}


class Stage80Tests(unittest.TestCase):
    def test_two_synthetic_headers_both_registry_names(self):
        for label in mod.NAM_PINS:
            h = mod.read_nam_header(nam(), label)
            self.assertEqual(h["architecture"], "SlimmableContainer")
            self.assertEqual(h["sample_rate_hz"], 48000)
            self.assertTrue(h["registered_in_stage77_original_pe"])
            self.assertFalse(h["model_weights_included_in_report"])

    def test_malformed_and_nonfinite_nam_headers_rejected(self):
        for bad in (True, "48000", 0, -44100, float("nan"), float("inf")):
            with self.subTest(rate=bad), self.assertRaises(ValueError):
                mod.read_nam_header(nam(rate=bad), "x")
        for bad in ("", None, 1):
            with self.subTest(architecture=bad), self.assertRaises(ValueError):
                mod.read_nam_header(nam(architecture=bad), "x")

    def test_duplicate_keys_and_json_constants_rejected(self):
        for data in (b'{"architecture":"WaveNet","architecture":"LSTM"}',
                     b'{"architecture":"WaveNet","sample_rate":NaN}'):
            with self.assertRaises(ValueError):
                mod.read_nam_header(data, "x")

    def test_unknown_architecture_never_registered(self):
        h = mod.read_nam_header(nam(architecture="UnrecognizedSynthetic"), "x")
        self.assertFalse(h["registered_in_stage77_original_pe"])

    def test_hash_pin_mismatch_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.nam"
            p.write_bytes(nam())
            with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
                mod.checked_file(p, "0" * 64, 100000)
            with self.assertRaisesRegex(ValueError, "oversized"):
                mod.checked_file(p, "0" * 64, 10)

    def test_synthetic_full_audit_preserves_unbound_capture_claims(self):
        names = {label: Path("synthetic_" + label + ".nam") for label in mod.NAM_PINS}
        clos = {label: Path("synthetic_" + label + ".clo") for label in mod.CLO_PINS}

        def fake_checked(path, expected, limit):
            return nam() if path.suffix == ".nam" else b"VTSI" + b"x" * 8836

        with (patch.object(mod.stage79, "audit", return_value=accepted_stage79()),
              patch.object(mod, "checked_file", side_effect=fake_checked),
              patch.object(mod, "exact_capture_completion_size", return_value=8840),
              patch.object(mod, "exact_model_identity_mentions", return_value=[])):
            report = mod.audit(Path("dll"), Path("capture"), names, clos)
        self.assertEqual(report["status"], mod.STATUS)
        self.assertTrue(report["clo_size_only_match_nonunique"])
        self.assertFalse(report["independent_stage64_input_nam_identity_proven"])
        self.assertFalse(report["claims"]["specific_stage64_native_factory_selected"])

    def test_stage79_drift_fails_closed(self):
        names = {label: Path("dummy.nam") for label in mod.NAM_PINS}
        clos = {label: Path("dummy.clo") for label in mod.CLO_PINS}
        for variant in ("status", "candidate", "factory"):
            report = accepted_stage79()
            if variant == "status":
                report["status"] = mod.stage79.STATUS_CANDIDATE
            elif variant == "candidate":
                report["stage64_metadata_inspection"]["candidate_count"] = 1
            else:
                report["claims"]["specific_stage64_factory_selected"] = True
            with self.subTest(variant=variant), patch.object(mod.stage79, "audit", return_value=report):
                with self.assertRaisesRegex(ValueError, "Stage79"):
                    mod.audit(Path("dll"), Path("stage64"), names, clos)

    def test_clo_size_is_not_input_identity(self):
        names = {label: Path("synthetic_" + label + ".nam") for label in mod.NAM_PINS}
        clos = {label: Path("synthetic_" + label + ".clo") for label in mod.CLO_PINS}

        def fake_checked(path, expected, limit):
            return nam() if path.suffix == ".nam" else b"x" * (8840 if "2203" in path.name else 8750)

        with (patch.object(mod.stage79, "audit", return_value=accepted_stage79()),
              patch.object(mod, "checked_file", side_effect=fake_checked),
              patch.object(mod, "exact_capture_completion_size", return_value=8840),
              patch.object(mod, "exact_model_identity_mentions", return_value=[])):
            report = mod.audit(Path("dll"), Path("capture"), names, clos)
        self.assertFalse(report["clo_size_only_match_nonunique"])
        self.assertFalse(report["independent_stage64_input_nam_identity_proven"])


if __name__ == "__main__":
    unittest.main()
