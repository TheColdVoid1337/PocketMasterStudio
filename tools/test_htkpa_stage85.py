"""Stage85 synthetic regression: exact argument-provenance pins and claim limits."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage85/audit_resampler_rate_arguments.py"
spec = importlib.util.spec_from_file_location("stage85_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def synthetic_insns():
    return {owner: {mod.BASE + rva: mod.stage72.normalize_asm(asm)
                    for rva, asm in pins.items()}
            for owner, pins in mod.PINS.items()}


class Stage85Tests(unittest.TestCase):
    def test_47_original_instruction_pins(self):
        result = mod.verify_lineage(synthetic_insns())
        self.assertEqual(result["checked_source_pin_count"], 47)
        self.assertEqual(len(result["exact_native_pin_groups"]), 7)

    def test_fifth_argument_callee_stack_equation(self):
        self.assertEqual(mod.stack_argument_entry_offset(), 0x28)

    def test_stack_prologue_mutation_rejected(self):
        for args in ({"push_count": 7}, {"rbp_negative": 0x27AA8},
                     {"rbp_positive": 0x27B18}):
            with self.subTest(args=args), self.assertRaisesRegex(ValueError, "ABI offset"):
                mod.stack_argument_entry_offset(**args)

    def test_bad_stack_count_rejected(self):
        with self.assertRaisesRegex(ValueError, "push count"):
            mod.stack_argument_entry_offset(push_count=100)

    def test_missing_function_owner_rejected(self):
        insns = synthetic_insns()
        insns.pop(0xCE00)
        with self.assertRaisesRegex(ValueError, "Missing owner"):
            mod.verify_lineage(insns)

    def test_interprocedural_fifth_argument_mutation_rejected(self):
        insns = synthetic_insns()
        insns[0x10E70][mod.BASE + 0x11093] = "movss dword ptr [rsp+0x28],xmm0"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_lineage(insns)

    def test_callee_stack_load_mutation_rejected(self):
        insns = synthetic_insns()
        insns[0x10230][mod.BASE + 0x10287] = "movss xmm6,dword ptr [rbp+0x27b28]"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_lineage(insns)

    def test_context_rate_field_mutation_rejected(self):
        insns = synthetic_insns()
        insns[0xBE830][mod.BASE + 0xBF358] = "movss xmm1,dword ptr [r14+0x20ebc]"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_lineage(insns)

    def test_alternate_context_writer_mutation_rejected(self):
        insns = synthetic_insns()
        insns[0xBFE00][mod.BASE + 0xC03AE] = "movss dword ptr [rdi+0x20ec4],xmm10"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_lineage(insns)

    def test_resampler_argument_swap_mutation_rejected(self):
        insns = synthetic_insns()
        insns[0xCE00][mod.BASE + 0xCFDB] = "cvtss2sd xmm2,xmm9"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_lineage(insns)

    def test_constructor_xmm_identity_mutation_rejected(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x11BD0] = "movaps xmm9,xmm1"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_lineage(insns)

    def test_previous_gate_rejects_runtime_parent_escalation(self):
        with patch.object(mod.stage84, "audit", return_value={
            "status": mod.stage84.STATUS,
            "claims": {"historical_stage64_active_child_verified": False,
                       "historical_stage64_resampler_parent_verified": True,
                       "same_run_nam_clo_sha_verified": False},
        }):
            with self.assertRaisesRegex(ValueError, "silently elevated"):
                mod.audit(Path("absent.dll"), Path("absent.tar.gz"), {}, {})


if __name__ == "__main__":
    unittest.main()
