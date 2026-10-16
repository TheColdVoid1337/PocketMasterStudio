"""Stage88 synthetic mutation tests: original direct group callsite families."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage88/audit_all_group_callsites.py"
spec = importlib.util.spec_from_file_location("stage88_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_insns():
    return {owner: {mod.BASE + rva: mod.stage72.normalize_asm(asm)
                    for rva, asm in pins.items()}
            for owner, pins in mod.PINS.items()}


def encoded_direct_call(rva, target=mod.GROUP_HELPER):
    return b"\xe8" + struct.pack("<i", target - (rva + 5))


def fake_pe_reader(blobs):
    def read(_data, rva, size):
        if rva not in blobs or size != len(blobs[rva]):
            raise ValueError("Synthetic PE RVA not backed")
        return blobs[rva]
    return read


class Stage88Tests(unittest.TestCase):
    def mutate(self, owner, rva, unexpected):
        insns = fake_insns()
        insns[owner][mod.BASE + rva] = unexpected
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_callsite_context(insns)

    def literals(self, blobs=None):
        if blobs is None:
            blobs = {rva: struct.pack("<d", value)
                     for rva, value in mod.ENUM_SOURCE_CONSTANTS.items()}
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=fake_pe_reader(blobs)):
            return mod.verify_rate_constants(b"FAKE_PE")

    def inventory(self, decoded=None, blobs=None):
        if decoded is None:
            decoded = sorted(mod.CALL_OWNERS)
        if blobs is None:
            blobs = {rva: encoded_direct_call(rva) for rva in mod.CALL_OWNERS}
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=fake_pe_reader(blobs)):
            return mod.verify_call_inventory(decoded, b"FAKE_PE")

    def test_six_original_direct_call_locations(self):
        result = self.inventory()
        self.assertEqual(result["direct_rel32_callsite_count"], 6)
        self.assertEqual(result["raw_original_e8_rel32_encoding_verified_count"], 6)
        self.assertEqual(len(result["newly_accounted_four"]), 4)
        self.assertEqual(len(result["stage87_previously_pinned_two"]), 2)

    def test_all_original_callers_have_four_expected_pdata_owners(self):
        self.assertEqual(set(mod.CALL_OWNERS.values()),
                         {0xD4A0, 0x11160, 0xBE830, 0xE2640})

    def test_inventory_omitted_direct_site_fails(self):
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.inventory(sorted(mod.CALL_OWNERS)[:-1])

    def test_inventory_unknown_direct_site_fails(self):
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.inventory(sorted([*mod.CALL_OWNERS, 0xABCDEF]))

    def test_inventory_wrong_call_target_fails(self):
        blobs = {rva: encoded_direct_call(rva) for rva in mod.CALL_OWNERS}
        blobs[0x113C4] = encoded_direct_call(0x113C4, 0xCF00)
        with self.assertRaisesRegex(ValueError, "different target"):
            self.inventory(blobs=blobs)

    def test_inventory_wrong_opcode_fails(self):
        blobs = {rva: encoded_direct_call(rva) for rva in mod.CALL_OWNERS}
        blobs[0xBF47F] = b"\xe9" + blobs[0xBF47F][1:]
        with self.assertRaisesRegex(ValueError, "not five-byte E8"):
            self.inventory(blobs=blobs)

    def test_direct_call_negative_rel32_is_signed(self):
        encoded = encoded_direct_call(0xE28F1)
        self.assertLess(struct.unpack_from("<i", encoded, 1)[0], 0)
        mod.verify_rel32_bytes(encoded, 0xE28F1)

    def test_truncated_direct_call_fails(self):
        with self.assertRaisesRegex(ValueError, "five-byte"):
            mod.verify_rel32_bytes(b"\xe8\x00", 0xD786)

    def test_parser_six_exact_call_lines(self):
        raw = "\n".join(f"  {mod.BASE + rva:x}:  call 0x{mod.BASE + mod.GROUP_HELPER:x}"
                        for rva in mod.CALL_OWNERS)
        self.assertEqual(mod.direct_calls_in_text(raw, mod.TEXT_START, mod.TEXT_END),
                         sorted(mod.CALL_OWNERS))

    def test_parser_ignores_indirect_and_wrong_target(self):
        raw = "\n".join([
            f" {mod.BASE + 0xD786:x}: call r10",
            f" {mod.BASE + 0x112A2:x}: call 0x{mod.BASE + 0xCF00:x}",
            f" {mod.BASE + 0xE28F1:x}: call 0x{mod.BASE + mod.GROUP_HELPER:x}",
        ])
        self.assertEqual(mod.direct_calls_in_text(raw, mod.TEXT_START, mod.TEXT_END),
                         [0xE28F1])

    def test_parser_ignores_out_of_text_instruction(self):
        raw = f" {mod.BASE + mod.TEXT_END + 10:x}: call 0x{mod.BASE + mod.GROUP_HELPER:x}"
        self.assertEqual(mod.direct_calls_in_text(raw, mod.TEXT_START, mod.TEXT_END), [])

    def test_parser_duplicate_instruction_rejected(self):
        row = f" {mod.BASE + 0xD786:x}: call 0x{mod.BASE + mod.GROUP_HELPER:x}"
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            mod.direct_calls_in_text(row + "\n" + row, mod.TEXT_START, mod.TEXT_END)

    def test_parser_output_size_bounded(self):
        with patch.object(mod, "MAX_DISASSEMBLY_CHARS", 8):
            with self.assertRaisesRegex(ValueError, "Unbounded"):
                mod.direct_calls_in_text(" " * 9, mod.TEXT_START, mod.TEXT_END)

    def test_original_enum_literal_rate_triplet(self):
        self.assertEqual(list(self.literals().values()), [44100, 48000, 96000])

    def test_mutate_enum_44100_literal_fails(self):
        blobs = {rva: struct.pack("<d", value)
                 for rva, value in mod.ENUM_SOURCE_CONSTANTS.items()}
        blobs[0x24CCF8] = struct.pack("<d", 48000.0)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.literals(blobs)

    def test_mutate_enum_48000_literal_fails(self):
        blobs = {rva: struct.pack("<d", value)
                 for rva, value in mod.ENUM_SOURCE_CONSTANTS.items()}
        blobs[0x24CD00] = struct.pack("<d", 44100.0)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.literals(blobs)

    def test_mutate_enum_96000_literal_fails(self):
        blobs = {rva: struct.pack("<d", value)
                 for rva, value in mod.ENUM_SOURCE_CONSTANTS.items()}
        blobs[0x24CD10] = struct.pack("<d", 96001.0)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.literals(blobs)

    def test_all_four_rate_family_contexts(self):
        result = mod.verify_callsite_context(fake_insns())
        self.assertEqual(len(result["four_rate_input_families"]), 4)
        self.assertEqual(len(result["verified_pin_rvas_by_pdata_owner"]), 4)
        self.assertEqual(result["checked_exact_instruction_pins"],
                         sum(map(len, mod.PINS.values())))
        self.assertFalse(result["same_run_stage64_specific_caller_determined"])
        self.assertTrue(result["stage64_reverse_ratio_not_unique_to_any_caller"])

    def test_missing_owner_rejected(self):
        insns = fake_insns()
        insns.pop(0x11160)
        with self.assertRaisesRegex(ValueError, "Missing owner"):
            mod.verify_callsite_context(insns)

    def test_d786_source_rate_field_mutation(self):
        self.mutate(0xD4A0, 0xD779, "movsd xmm1,qword ptr [r14+0x18]")

    def test_d786_incoming_target_rate_mutation(self):
        self.mutate(0xD4A0, 0xD4D2, "movaps xmm6,xmm1")

    def test_d786_direct_call_mutation(self):
        self.mutate(0xD4A0, 0xD786, "call 0x18000cf00")

    def test_enum_selector_field_mutation(self):
        self.mutate(0x11160, 0x1119A, "movzx ecx,word ptr [rcx+0xc]")

    def test_enum_rate_branch_mutation(self):
        self.mutate(0x11160, 0x111AA, "jne 0x1800111b6")

    def test_enum_first_segment_call_mutation(self):
        self.mutate(0x11160, 0x112A2, "call 0x18000cf00")

    def test_enum_second_segment_call_mutation(self):
        self.mutate(0x11160, 0x113C4, "call 0x18000cf00")

    def test_context_second_input_buffer_mutation(self):
        self.mutate(0xBE830, 0xBF440, "mov rax,qword ptr [r14+0x24408]")

    def test_context_second_rate_field_mutation(self):
        self.mutate(0xBE830, 0xBF473, "movss xmm1,dword ptr [r14+0x20ec4]")

    def test_context_second_direct_call_mutation(self):
        self.mutate(0xBE830, 0xBF47F, "call 0x18000cf00")

    def test_context_guard_mutation(self):
        self.mutate(0xBE830, 0xBE89B, "cmp byte ptr [rcx+0x243db],0x0")

    def test_fixed_target_rate_mutation(self):
        self.mutate(0xE2640, 0xE28E6, "movss xmm2,dword ptr [rip+0x16a503]")

    def test_prior_stage87_runtime_escalation_rejected(self):
        with patch.object(mod.stage87, "audit", return_value={
            "status": mod.stage87.STATUS,
            "claims": {
                "historical_stage64_specific_parent_pointer_or_callsite_verified": True,
                "stage64_same_run_nam_clo_sha_authenticated": False,
                "actual_stage64_input_48000_verified": False,
                "original_dll_executed": False,
            },
        }):
            with self.assertRaisesRegex(ValueError, "silently elevated"):
                mod.audit(Path("absent.dll"), Path("absent.tar.gz"), {}, {})


if __name__ == "__main__":
    unittest.main()
