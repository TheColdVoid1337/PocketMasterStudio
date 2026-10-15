"""Stage82 fail-closed offline tests with entirely synthetic source bytes."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage82/audit_slimmable_submodels.py"
spec = importlib.util.spec_from_file_location("stage82_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def instruction_sample() -> dict[int, str]:
    return {
        mod.stage72.BASE + rva: mod.stage72.normalize_asm(op)
        for pins in mod.PINS.values() for rva, op in pins.items()
    }


def synthetic_constants(_data: bytes, rva: int, length: int) -> bytes:
    assert length == 8
    if rva == 0x24C918:
        return struct.pack("<d", 1.0)
    if rva == 0x24CED0:
        return struct.pack("<d", -1.0)
    raise AssertionError(f"Unexpected constant at {rva:#x}")


class Stage82Tests(unittest.TestCase):
    def verify(self, insns: dict[int, str] | None = None) -> dict:
        with (patch.object(mod.stage77, "read_literal", return_value="synthetic") as strings,
              patch.object(mod.stage72, "pe_file_bytes", side_effect=synthetic_constants)):
            report = mod.verify_nested_source(
                insns if insns is not None else instruction_sample(), b"SYNTHETIC")
            self.assertEqual(strings.call_count, 3)
        return report

    def test_static_nested_model_dispatch_and_rate_guards(self):
        report = self.verify()
        self.assertEqual(
            sum(map(len, report["validated_instruction_groups"].values())),
            sum(map(len, mod.PINS.values())))
        self.assertEqual(report["nested_model_parser_rva"], "0xcb200")
        self.assertEqual(report["nested_model_packet_dispatch_rva"], "0xca760")
        self.assertEqual(report["element_record_layout"],
                         "16 bytes: f64 max_value, then nested-model pointer")
        self.assertEqual(report["float_constants"]["unknown_rate_sentinel"], -1.0)
        self.assertTrue(report["static_path_conditional"])

    def test_nested_parser_call_mutation_fails_closed(self):
        insns = instruction_sample()
        insns[mod.stage72.BASE + 0xC5A7F] = "call 0x1800cc4e0"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_different_max_value_key_load_fails_closed(self):
        insns = instruction_sample()
        insns[mod.stage72.BASE + 0xC5936] = "lea rdx,[rip+0xc9aeb+0x2]"
        with self.assertRaises(ValueError):
            self.verify(insns)

    def test_nested_rate_field_offset_mutation_fails_closed(self):
        insns = instruction_sample()
        insns[mod.stage72.BASE + 0xC60B4] = "movsd xmm6,qword ptr [rax+0x20]"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_threshold_sorting_condition_mutation_fails_closed(self):
        insns = instruction_sample()
        insns[mod.stage72.BASE + 0xC606F] = "jb 0x1800c626c"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_bad_last_maximum_constant_rejected(self):
        def changed(data: bytes, rva: int, length: int) -> bytes:
            if rva == 0x24C918:
                return struct.pack("<d", 0.5)
            return synthetic_constants(data, rva, length)
        with (patch.object(mod.stage77, "read_literal", return_value="synthetic"),
              patch.object(mod.stage72, "pe_file_bytes", side_effect=changed)):
            with self.assertRaisesRegex(ValueError, "Native constant changed"):
                mod.verify_nested_source(instruction_sample(), b"SYNTHETIC")

    def test_missing_rate_sentinel_mutation_rejected(self):
        def changed(data: bytes, rva: int, length: int) -> bytes:
            if rva == 0x24CED0:
                return struct.pack("<d", 0.0)
            return synthetic_constants(data, rva, length)
        with (patch.object(mod.stage77, "read_literal", return_value="synthetic"),
              patch.object(mod.stage72, "pe_file_bytes", side_effect=changed)):
            with self.assertRaisesRegex(ValueError, "Native constant changed"):
                mod.verify_nested_source(instruction_sample(), b"SYNTHETIC")

    def test_prior_stage81_wrong_status_fails_before_reading_sources(self):
        with patch.object(mod.stage81, "audit", return_value={"status": "other"}):
            with self.assertRaisesRegex(ValueError, "Stage81"):
                mod.audit(Path("none.dll"), Path("none.tar.gz"), {}, {})

    def test_runtime_claim_in_stage81_is_rejected(self):
        with patch.object(mod.stage81, "audit", return_value={
            "status": mod.stage81.STATUS,
            "claims": {"stage64_selected_submodel_or_factory_verified": True},
        }):
            with self.assertRaisesRegex(ValueError, "runtime factory"):
                mod.audit(Path("none.dll"), Path("none.tar.gz"), {}, {})

    def test_exact_bounded_literals_requested(self):
        with (patch.object(mod.stage77, "read_literal", return_value="synthetic") as reader,
              patch.object(mod.stage72, "pe_file_bytes", side_effect=synthetic_constants)):
            mod.verify_nested_source(instruction_sample(), b"SYNTHETIC")
        self.assertEqual(
            [call.args[1:] for call in reader.call_args_list],
            [(0x18F438, "submodels", 9),
             (0x18F428, "max_value", 9),
             (0x18CD34, "model", 5)])


if __name__ == "__main__":
    unittest.main()
