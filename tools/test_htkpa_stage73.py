"""Stage73 source-only offline tests; synthetic CFG/PE, never runs vendor DLL."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage73/audit_incoming_rate.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage73", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def cfg(seq):
    return {mod.BASE + rva: asm for rva, asm in seq}


def two_source_cfg():
    return cfg([
        (0xE0E0, "test eax,eax"),
        (0xE0E2, "je 0x18000e9ea"),
        (0xE855, "movsd xmm9,qword ptr [rbx+0x18]"),
        (0xE85B, "cvtpd2ps xmm9,xmm9"),
        (0xE860, "jmp 0x18000f620"),
        (0xE9EA, "movss xmm9,dword ptr [rip+0x23e401]"),
        (0xE9F3, "jmp 0x18000f620"),
        (0xF620, "cvttss2si ebx,xmm9"),
    ])


class Stage73Tests(unittest.TestCase):
    def test_exact_sha_pins_source_only_and_runtime_negative_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(sum(map(len, mod.PINS.values())), 34)
        self.assertEqual(mod.PINS["shared_rate_helper_0xe0e0"][0xE9EA],
                         "movss xmm9,dword ptr [rip+0x23e401]")
        self.assertEqual(mod.PE_F32, {0x24CDF0: 44100.0, 0x24CDF4: 48000.0})
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ctypes.CDLL", source)
        self.assertNotIn("frida.attach", source)
        self.assertIn('"actual_stage64_reverse_parent_verified": False', source)
        self.assertIn('"real_48000_fallback_branch_observed_running": False', source)

    def test_all_exact_source_pins_fail_on_modified_instruction(self):
        instructions = {mod.BASE + rva: mod.stage72.normalize_asm(asm)
                        for group in mod.PINS.values() for rva, asm in group.items()}
        matched = mod.stage72.verify_pins(mod.PINS, instructions)
        self.assertEqual(sum(map(len, matched.values())), 34)
        changed = dict(instructions)
        changed[mod.BASE + 0xE9EA] = "movss xmm9,dword ptr [rip+0x23e405]"
        with self.assertRaisesRegex(ValueError, "0xe9ea"):
            mod.stage72.verify_pins(mod.PINS, changed)

    def test_two_cfg_sources_only_if_both_assignments_reach_conversion(self):
        result = mod.xmm9_cfg(two_source_cfg())
        self.assertEqual(set(result["possible_xmm9_sources"]), {
            "f64_metadata_object_plus_0x18_to_f32", "conditional_f32_fallback_48000"})
        self.assertTrue(result["closed_local_set_on_decoded_paths"])
        self.assertFalse(result["runtime_source_selected"])
        self.assertEqual(result["unresolved_local_jump_sites"], [])

    def test_cfg_bypass_assignment_is_explicit_unknown(self):
        seq = two_source_cfg()
        seq[mod.BASE + 0xE0E0] = "je 0x18000f620"
        seq[mod.BASE + 0xE0E2] = "je 0x18000e9ea"
        result = mod.xmm9_cfg(seq)
        self.assertIn("ENTRY_UNKNOWN", result["possible_xmm9_sources"])
        self.assertFalse(result["closed_local_set_on_decoded_paths"])

    def test_indirect_jump_and_budget_never_imply_complete_graph(self):
        seq = two_source_cfg()
        seq[mod.BASE + 0xE0E2] = "jmp rax"
        indirect = mod.xmm9_cfg(seq)
        self.assertFalse(indirect["closed_local_set_on_decoded_paths"])
        self.assertIn("0xe0e2:UNRESOLVED_JUMP", indirect["unresolved_local_jump_sites"])
        with patch.object(mod, "MAX_SOURCE_STATES", 1):
            limited = mod.xmm9_cfg(two_source_cfg())
        self.assertFalse(limited["closed_local_set_on_decoded_paths"])
        self.assertIn("BUDGET_EXCEEDED", limited["unresolved_local_jump_sites"])

    def test_unknown_xmm9_write_invalidates_closed_source_set_but_compare_does_not(self):
        seq = two_source_cfg()
        seq[mod.BASE + 0xE9F3] = "xorps xmm9,xmm9"
        other = mod.xmm9_cfg(seq)
        self.assertIn("OTHER_XMM9_DEFINITION", other["possible_xmm9_sources"])
        self.assertFalse(other["closed_local_set_on_decoded_paths"])
        seq[mod.BASE + 0xE9F3] = "ucomiss xmm9,dword ptr [rip+0x23e3e7]"
        comparison = mod.xmm9_cfg(seq)
        self.assertTrue(comparison["closed_local_set_on_decoded_paths"])

    def test_pinned_native_values_are_file_backed_not_assumed(self):
        raw = bytearray(synthetic_pe())
        struct.pack_into("<f", raw, 0x410, 48000.0)
        val = struct.unpack("<f", mod.stage72.pe_file_bytes(bytes(raw), 0x1010, 4))[0]
        self.assertEqual(val, 48000.0)
        with self.assertRaisesRegex(ValueError, "not uniquely file-backed"):
            mod.stage72.pe_file_bytes(bytes(raw), 0x24CDF4, 4)

    def test_sha_gate_rejects_synthetic_unpinned_vendor_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "5868USB.dll"
            fixture.write_bytes(synthetic_pe())
            with self.assertRaisesRegex(ValueError, "SHA"):
                mod.stage72.previous.verify_dll(fixture)


if __name__ == "__main__":
    unittest.main()
