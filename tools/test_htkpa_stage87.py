"""Stage87 synthetic tests for original conditional two-level virtual dispatch."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage87/audit_fractional_dispatch_chain.py"
spec = importlib.util.spec_from_file_location("stage87_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def synthetic_insns():
    return {owner: {mod.BASE + rva: mod.stage72.normalize_asm(asm)
                    for rva, asm in pins.items()}
            for owner, pins in mod.PINS.items()}


def synthetic_pe():
    blobs = {}
    for table in (mod.PARENT_VTABLE_RVA, mod.PARENT_CTOR_VTABLE_RVA):
        for i, target in enumerate(mod.PARENT_VTABLE_TARGETS):
            blobs[table + i * 8] = struct.pack("<Q", mod.BASE + target)
    for i, target in enumerate(mod.stage86.VTABLE_TARGETS):
        blobs[mod.stage86.FRACTIONAL_VTABLE_RVA + i * 8] = struct.pack(
            "<Q", mod.BASE + target)
    blobs[mod.FIXED_TARGET_F32_RVA] = struct.pack("<f", 44100.0)
    return blobs


def fake_pe_reader(blobs):
    def read(_data, rva, size):
        if rva not in blobs or size != len(blobs[rva]):
            raise ValueError("Synthetic file-backed PE range absent")
        return blobs[rva]
    return read


class Stage87Tests(unittest.TestCase):
    def vtables(self, blobs=None):
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=fake_pe_reader(
                blobs if blobs is not None else synthetic_pe())):
            return mod.verify_parent_vtables(b"FAKE_PE")

    def mutated_pin(self, owner, rva, wrong):
        insns = synthetic_insns()
        insns[owner][mod.BASE + rva] = wrong
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_route(insns)

    def test_parent_and_child_original_virtual_method_slots(self):
        result = self.vtables()
        self.assertEqual(len(result["original_parent_vtables"]), 2)
        for table in result["original_parent_vtables"].values():
            self.assertEqual(table["seven_qword_method_targets"]["+0x30"], "0x11850")
        self.assertEqual(result["child_slot_0x30_target"], "0x135c0")

    def test_mutate_group_parent_dispatch_slot_fails(self):
        blobs = synthetic_pe()
        blobs[mod.PARENT_VTABLE_RVA + 0x30] = struct.pack("<Q", mod.BASE + 0x11920)
        with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
            self.vtables(blobs)

    def test_mutate_constructor_initial_dispatch_slot_fails(self):
        blobs = synthetic_pe()
        blobs[mod.PARENT_CTOR_VTABLE_RVA + 0x30] = struct.pack("<Q", mod.BASE + 0x11AD0)
        with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
            self.vtables(blobs)

    def test_mutate_child_hook_slot_fails(self):
        blobs = synthetic_pe()
        blobs[mod.stage86.FRACTIONAL_VTABLE_RVA + 0x30] = struct.pack("<Q", mod.BASE + 0x135C8)
        with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
            self.vtables(blobs)

    def test_mutate_shared_output_rate_pe_literal_fails(self):
        blobs = synthetic_pe()
        blobs[mod.FIXED_TARGET_F32_RVA] = struct.pack("<f", 48000.0)
        with self.assertRaisesRegex(ValueError, "44100"):
            self.vtables(blobs)

    def test_all_exact_pins_and_conditional_claims(self):
        result = mod.verify_route(synthetic_insns())
        self.assertEqual(result["new_checked_instruction_pin_count"], 60)
        self.assertEqual(len(result["verified_instruction_rvas_by_source_owner"]), 5)
        self.assertFalse(result["same_run_stage64_exact_parent_or_caller_observed"])
        self.assertTrue(result["conditional_parent_and_child_object_types_required"])

    def test_missing_function_owner_fails(self):
        insns = synthetic_insns()
        insns.pop(0x11850)
        with self.assertRaisesRegex(ValueError, "Missing source owner"):
            mod.verify_route(insns)

    def test_alternate_helper_source_field_provenance(self):
        self.mutated_pin(0xE2640, 0xE28DC, "movsd xmm1,qword ptr [r14+0x18]")

    def test_alternate_helper_direct_call_mutation(self):
        self.mutated_pin(0xE2640, 0xE28F1, "call 0x18000cf00")

    def test_nam_helper_source_field_mutation(self):
        self.mutated_pin(0xBE830, 0xBF358, "movss xmm1,dword ptr [r14+0x20ec4]")

    def test_parent_constructor_direct_call_mutation(self):
        self.mutated_pin(0xCE00, 0xCFF3, "call 0x180011b50")

    def test_group_parent_vtable_install_mutation(self):
        self.mutated_pin(0xCE00, 0xCFF8, "mov qword ptr [rbx+0x8],r15")

    def test_group_parent_array_store_mutation(self):
        self.mutated_pin(0xCE00, 0xD018, "mov qword ptr [rdi+0x8],rbx")

    def test_group_parent_vslot_read_mutation(self):
        self.mutated_pin(0xCE00, 0xD0F7, "mov r10,qword ptr [rax+0x28]")

    def test_group_indirect_dispatch_call_mutation(self):
        self.mutated_pin(0xCE00, 0xD10E, "call r11")

    def test_parent_first_stage_vslot_mutation(self):
        self.mutated_pin(0x11850, 0x118B1, "call qword ptr [rax+0x28]")

    def test_parent_child_pointer_offset_mutation(self):
        self.mutated_pin(0x11850, 0x118FD, "mov rcx,qword ptr [rbx+0x58]")

    def test_parent_child_hook_vslot_mutation(self):
        self.mutated_pin(0x11850, 0x11909, "call qword ptr [rax+0x20]")

    def test_original_constructor_parent_base_vtable_mutation(self):
        self.mutated_pin(0x11B60, 0x11BD7, "lea rax,[rip+0x23341b]")

    def test_prior_stage86_runtime_escalation_rejected(self):
        with patch.object(mod.stage86, "audit", return_value={
            "status": mod.stage86.STATUS,
            "claims": {
                "historical_stage64_specific_parent_pointer_or_caller_verified": True,
                "historical_stage64_nam_container_pointer_parent_bound": False,
                "stage64_same_run_nam_clo_sha_authenticated": False,
                "original_dll_executed": False,
            },
        }):
            with self.assertRaisesRegex(ValueError, "elevated"):
                mod.audit(Path("absent.dll"), Path("absent.tar.gz"), {}, {})


if __name__ == "__main__":
    unittest.main()
