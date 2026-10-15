"""Stage72 offline regression tests; synthetic instructions/PE, no vendor code."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage72/audit_rate_provenance.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage72", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def cfg(seq):
    return {mod.BASE + rva: op for rva, op in seq}


class Stage72Tests(unittest.TestCase):
    def test_exact_pins_and_static_only_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(mod.FLOAT44100_RVA, 0x24CDF0)
        self.assertEqual(sum(map(len, mod.PINS.values())), 57)
        self.assertEqual(mod.PINS["wav_reader_branch"][0x8BE8D],
                         "movsd qword ptr [rdi+0x8],xmm0")
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ctypes.CDLL", script)
        self.assertNotIn("frida.attach", script)
        self.assertIn('"actual_stage64_reverse_parent_verified": False', script)
        self.assertIn('"live_original_source_rate_48000_verified": False', script)

    def test_llvm_and_gnu_intel_disassembly_normalize_equivalently(self):
        llvm = """1800bf358: movss xmm1, dword ptr [r14 + 0x20ec0]
1800bf364: call 0x18000ce00
"""
        gnu = """research/test.dll: file format pei-x86-64
   1800bf358:\tmovss  xmm1,DWORD PTR [r14+0x20ec0]
   1800bf364:\tcall   0x18000ce00\t# an explanatory comment
"""
        expected = cfg([(0xBF358, "movss xmm1,dword ptr [r14+0x20ec0]"),
                        (0xBF364, "call 0x18000ce00")])
        self.assertEqual(mod.parse_disassembly(llvm, 0xBF358, 0xBF369), expected)
        self.assertEqual(mod.parse_disassembly(gnu, 0xBF358, 0xBF369), expected)
        with self.assertRaisesRegex(ValueError, "No original-PE"):
            mod.parse_disassembly(gnu, 0x100, 0x200)

    def test_all_pin_groups_must_match_exact_original_addresses(self):
        all_instructions = {mod.BASE + rva: mod.normalize_asm(asm)
                            for group in mod.PINS.values()
                            for rva, asm in group.items()}
        accepted = mod.verify_pins(mod.PINS, all_instructions)
        self.assertEqual(sum(map(len, accepted.values())), 57)
        mutated = dict(all_instructions)
        mutated[mod.BASE + 0xBFEF9] = "movss dword ptr [rdi+0x20ec4],xmm10"
        with self.assertRaisesRegex(ValueError, "0xbfef9"):
            mod.verify_pins(mod.PINS, mutated)

    def test_file_backed_float32_44100_and_fail_closed_sections(self):
        data = bytearray(synthetic_pe())
        # Synthetic .text section: RVA 0x1010 maps to raw offset 0x410.
        struct.pack_into("<f", data, 0x410, 44100.0)
        self.assertEqual(struct.unpack("<f", mod.pe_file_bytes(bytes(data), 0x1010, 4))[0],
                         44100.0)
        with self.assertRaisesRegex(ValueError, "not uniquely file-backed"):
            mod.pe_file_bytes(bytes(data), 0x800000, 4)
        with self.assertRaisesRegex(ValueError, "Invalid PE"):
            mod.pe_file_bytes(b"invalid", 0x1010, 4)

    def test_local_cfg_one_reaching_r14_assignment_from_all_branches(self):
        insns = cfg([
            (0x100, "test eax,eax"),
            (0x102, "je 0x180000109"),
            (0x104, "mov r14,rcx"),
            (0x106, "jmp 0x180000110"),
            (0x109, "mov r14,rcx"),
            (0x110, "movss xmm1,dword ptr [r14+0x20ec0]"),
            (0x120, "ret"),
        ])
        # Move both branches through exactly the same pinned assignment by
        # making the conditional branch target the single assignment.
        insns[mod.BASE + 0x102] = "je 0x180000104"
        out = mod.local_r14_cfg(insns, start_rva=0x100, target_rva=0x110,
                                assignment_rva=0x104, label="entry_rcx")
        self.assertEqual(out["possible_r14_states_at_target"], ["entry_rcx"])
        self.assertTrue(out["unique_local_r14_assignment_on_decoded_paths"])
        self.assertFalse(out["runtime_object_identity_proven"])

    def test_cfg_branch_bypass_and_indirect_jump_remain_unproven(self):
        seq = cfg([
            (0x100, "je 0x180000110"),
            (0x104, "mov r14,rcx"),
            (0x108, "nop"),
            (0x110, "movss xmm1,dword ptr [r14+0x20ec0]"),
        ])
        out = mod.local_r14_cfg(seq, start_rva=0x100, target_rva=0x110,
                                assignment_rva=0x104, label="entry_rcx")
        self.assertEqual(set(out["possible_r14_states_at_target"]),
                         {"ENTRY_UNTRACED", "entry_rcx"})
        self.assertFalse(out["unique_local_r14_assignment_on_decoded_paths"])
        seq[mod.BASE + 0x100] = "jmp rax"
        indirect = mod.local_r14_cfg(seq, start_rva=0x100, target_rva=0x110,
                                     assignment_rva=0x104, label="entry_rcx")
        self.assertFalse(indirect["unique_local_r14_assignment_on_decoded_paths"])
        self.assertEqual(indirect["possible_r14_states_at_target"], [])
        self.assertTrue(indirect["unresolved_branch_sites"])

    def test_cfg_other_r14_write_invalidates_unique_provenance(self):
        insns = cfg([(0x100, "mov r14,rcx"), (0x104, "lea r14,[rsp+0x10]"),
                     (0x110, "movss xmm1,dword ptr [r14+0x20ec0]")])
        result = mod.local_r14_cfg(insns, start_rva=0x100, target_rva=0x110,
                                   assignment_rva=0x100, label="entry_rcx")
        self.assertEqual(result["possible_r14_states_at_target"], ["OTHER_R14_WRITE"])
        self.assertFalse(result["unique_local_r14_assignment_on_decoded_paths"])
        insns[mod.BASE + 0x104] = "xor r14,r14"
        arithmetic = mod.local_r14_cfg(insns, start_rva=0x100, target_rva=0x110,
                                       assignment_rva=0x100, label="entry_rcx")
        self.assertEqual(arithmetic["possible_r14_states_at_target"], ["OTHER_R14_WRITE"])

    def test_dual_backend_detection_and_bounded_disassembly(self):
        class Version:
            returncode = 0
            stdout = "GNU objdump (GNU Binutils) 2.43"
        with patch.object(mod.shutil, "which", return_value="/usr/bin/objdump"), \
                patch.object(mod.subprocess, "run", return_value=Version()):
            self.assertEqual(mod.select_objdump(None), ("/usr/bin/objdump", "GNU"))
        with self.assertRaisesRegex(ValueError, "Out-of-bounds"):
            mod.read_disassembly(Path("fake.dll"), "objdump", "GNU", 0, 99999)
        with self.assertRaisesRegex(ValueError, "Unknown disassembler"):
            mod.read_disassembly(Path("fake.dll"), "objdump", "unsupported", 0, 10)


if __name__ == "__main__":
    unittest.main()
