"""Stage83 synthetic PE anchors and threshold-boundary regressions."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage83/audit_slimmable_selection.py"
spec = importlib.util.spec_from_file_location("stage83_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def native_sample() -> dict[int, str]:
    return {mod.stage72.BASE + rva: mod.stage72.normalize_asm(op)
            for group in mod.PINS.values() for rva, op in group.items()}


class Stage83Tests(unittest.TestCase):
    def verify(self, insns: dict[int, str] | None = None) -> dict:
        with patch.object(mod.stage77, "read_pointer",
                          side_effect=lambda _data, _slot, target: f"0x{target:x}"):
            return mod.verify_native_selection(
                insns if insns is not None else native_sample(), b"SYNTHETIC")

    def test_all_exact_native_pins_and_vtable_routes(self):
        result = self.verify()
        self.assertEqual(
            sum(map(len, result["validated_instruction_groups"].values())),
            sum(map(len, mod.PINS.values())))
        self.assertEqual(result["vtable_slots_resolved"]["secondary_threshold_selector_virtual_0x8"],
                         "0xc5d30")
        self.assertEqual(result["array_begin_object_offset"], "0x58")
        self.assertEqual(result["current_child_index_object_offset"], "0x70")
        self.assertTrue(result["boundary_at_equal_threshold_advances_to_next_child"])
        self.assertFalse(result["stage64_control_value_observed"])

    def test_exact_six_pointer_slots_requested(self):
        with patch.object(mod.stage77, "read_pointer",
                          side_effect=lambda _data, _slot, target: f"0x{target:x}") as check:
            mod.verify_native_selection(native_sample(), b"SYNTHETIC")
        self.assertEqual([c.args[1:] for c in check.call_args_list],
                         list(mod.VTABLE_SLOTS.values()))

    def test_vtable_slot_mutation_fails_closed(self):
        def mutated(_data: bytes, slot: int, target: int) -> str:
            if slot == mod.SECONDARY_VTABLE_RVA + 8:
                raise ValueError("PE vtable slot mismatch")
            return f"0x{target:x}"
        with patch.object(mod.stage77, "read_pointer", side_effect=mutated):
            with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
                mod.verify_native_selection(native_sample(), b"SYNTHETIC")

    def test_selector_ja_branch_mutation_rejected(self):
        insns = native_sample()
        insns[mod.stage72.BASE + 0xC5D69] = "jae 0x1800c5d79"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_selected_child_virtual_slot_mutation_rejected(self):
        insns = native_sample()
        insns[mod.stage72.BASE + 0xC5DD2] = "call qword ptr [rax+0x18]"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_constructor_secondary_vtable_offset_mutation_rejected(self):
        insns = native_sample()
        insns[mod.stage72.BASE + 0xC5FF6] = "mov qword ptr [rdi+0x58],rax"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_selected_tail_dispatch_slot_mutation_rejected(self):
        insns = native_sample()
        insns[mod.stage72.BASE + 0xC5F33] = "jmp qword ptr [rax+0x18]"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            self.verify(insns)

    def test_exact_half_threshold_advances_to_second_child(self):
        maxima = [0.5, 1.0]
        cases = [(-0.01, 0), (0.0, 0), (0.499999, 0), (0.5, 1),
                 (0.75, 1), (1.0, 1), (1.01, 1)]
        for control, expected in cases:
            with self.subTest(control=control):
                self.assertEqual(mod.select_index(maxima, control), expected)

    def test_general_three_child_ordered_selector(self):
        maxima = [0.25, 0.5, 1.0]
        self.assertEqual(mod.select_index(maxima, 0.249), 0)
        self.assertEqual(mod.select_index(maxima, 0.25), 1)
        self.assertEqual(mod.select_index(maxima, 0.50), 2)
        self.assertEqual(mod.select_index(maxima, 20.0), 2)

    def test_reject_empty_unsorted_nonfinite_and_bool_thresholds(self):
        for values in ([], [0.5, 0.5], [0.5, 0.4],
                       [0.5, float("nan")], [0.5, float("inf")],
                       [True, 1.0], [0.5] * (mod.stage81.MAX_SUBMODELS + 1)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                mod.select_index(values, 0.1)

    def test_reject_nonfinite_or_bool_control(self):
        for value in (float("nan"), float("inf"), -float("inf"),
                      True, "0.5", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                mod.select_index([0.5, 1.0], value)

    def test_prior_stage82_mismatch_rejected_before_original_files(self):
        with patch.object(mod.stage82, "audit", return_value={"status": "not-stage82"}):
            with self.assertRaisesRegex(ValueError, "Stage82"):
                mod.audit(Path("none.dll"), Path("none.tar.gz"), {}, {})

    def test_claim_of_runtime_factory_selection_in_stage82_rejected(self):
        with patch.object(mod.stage82, "audit", return_value={
            "status": mod.stage82.STATUS,
            "claims": {"stage64_active_factory_verified": True},
        }):
            with self.assertRaisesRegex(ValueError, "Stage82"):
                mod.audit(Path("none.dll"), Path("none.tar.gz"), {}, {})


if __name__ == "__main__":
    unittest.main()
