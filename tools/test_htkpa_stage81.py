"""Stage81 offline regressions: synthetic NAM JSON and instruction pins only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage81/audit_sample_rate_ingress.py"
spec = importlib.util.spec_from_file_location("stage81_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def example() -> dict:
    def nested():
        return {"architecture": "WaveNet", "version": "0.7.0",
                "sample_rate": 48000.0, "config": {"layers": [{}]},
                "weights": {"synthetic-only": [1, 2, 3]},
                "metadata": {"private-key": "do-not-report"}}
    return {"architecture": "SlimmableContainer", "version": "0.7.0",
            "sample_rate": 48000.0, "config": {"submodels": [
                {"max_value": 0.5, "model": nested()},
                {"max_value": 1.0, "model": nested()}]},
            "weights": {"synthetic-only": [4]},
            "metadata": {"private-key": "do-not-report"}}


def read(obj: dict) -> dict:
    return mod.nested_nam_structure(json.dumps(obj).encode(), "synthetic")


def native_instructions() -> dict:
    return {mod.stage72.BASE + rva: mod.stage72.normalize_asm(op)
            for pins in mod.PINS.values() for rva, op in pins.items()}


class Stage81Tests(unittest.TestCase):
    def test_two_synthetic_wavenet_submodels_are_reported_without_weights(self):
        report = read(example())
        self.assertEqual(report["top_level_architecture"], "SlimmableContainer")
        self.assertEqual([item["architecture"] for item in report["submodels"]],
                         ["WaveNet", "WaveNet"])
        self.assertEqual([item["max_value"] for item in report["submodels"]], [0.5, 1.0])
        self.assertEqual(report["submodel_count"], 2)
        self.assertFalse(report["runtime_selected_submodel_identified"])
        self.assertNotIn("do-not-report", json.dumps(report))
        self.assertNotIn("synthetic-only", json.dumps(report))

    def test_wrong_top_level_architecture_rejected(self):
        obj = example()
        obj["architecture"] = "WaveNet"
        with self.assertRaisesRegex(ValueError, "SlimmableContainer"):
            read(obj)

    def test_wrong_outer_rate_or_version_rejected(self):
        for key, bad in (("sample_rate", 44100), ("sample_rate", True),
                         ("version", "0.6.0")):
            obj = example()
            obj[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                read(obj)

    def test_missing_or_oversized_nested_models_rejected(self):
        for subs in ([], [{}] * (mod.MAX_SUBMODELS + 1), None):
            obj = example()
            obj["config"]["submodels"] = subs
            with self.subTest(subs_type=str(type(subs))), self.assertRaises(ValueError):
                read(obj)

    def test_threshold_not_increasing_rejected(self):
        for bad in (0.5, 0.1, True, -0.1, 1.5, float("nan")):
            obj = example()
            obj["config"]["submodels"][1]["max_value"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                read(obj)

    def test_nested_wrong_architecture_rate_or_version_rejected(self):
        for key, bad in (("architecture", "LSTM"), ("sample_rate", 96000),
                         ("version", "0.8.0"), ("config", None)):
            obj = example()
            obj["config"]["submodels"][0]["model"][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                read(obj)

    def test_duplicate_keys_and_nan_constant_rejected(self):
        for payload in (b'{"architecture":"WaveNet","architecture":"WaveNet"}',
                        b'{"architecture":"SlimmableContainer","sample_rate":NaN}'):
            with self.assertRaises(ValueError):
                mod.nested_nam_structure(payload, "synthetic")

    def test_non_object_submodel_rejected(self):
        obj = example()
        obj["config"]["submodels"][0] = "bad"
        with self.assertRaisesRegex(ValueError, "submodel object"):
            read(obj)

    def test_native_exact_19_pins_key_targets_and_sentinel(self):
        insns = native_instructions()
        with (patch.object(mod.stage77, "read_literal", return_value="sample_rate") as literal,
              patch.object(mod.stage72, "pe_file_bytes", return_value=struct.pack("<d", -1.0))):
            report = mod.verify_native_rate_source(insns, b"SYNTHETIC")
        self.assertEqual(sum(map(len, report["validated_instruction_groups"].values())), 19)
        self.assertEqual(report["metadata_field_offset"], "0x78")
        self.assertEqual(report["missing_value_source_constant"], -1.0)
        self.assertEqual(literal.call_count, 2)

    def test_native_instruction_mutation_fails_closed(self):
        insns = native_instructions()
        insns[mod.stage72.BASE + 0xCB5F2] = "movsd qword ptr [r14+0x70],xmm0"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_native_rate_source(insns, b"SYNTHETIC")

    def test_native_missing_value_constant_mutation_fails_closed(self):
        with (patch.object(mod.stage77, "read_literal", return_value="sample_rate"),
              patch.object(mod.stage72, "pe_file_bytes", return_value=struct.pack("<d", 0.0))):
            with self.assertRaisesRegex(ValueError, "sentinel changed"):
                mod.verify_native_rate_source(native_instructions(), b"SYNTHETIC")

    def test_stage80_drift_rejected_before_private_reads(self):
        bad = {"status": mod.stage80.STATUS,
               "independent_stage64_input_nam_identity_proven": True}
        with patch.object(mod.stage80, "audit", return_value=bad):
            with self.assertRaisesRegex(ValueError, "Stage80"):
                mod.audit(Path("not-found-dll"), Path("not-found-stage64"), {}, {})


if __name__ == "__main__":
    unittest.main()
