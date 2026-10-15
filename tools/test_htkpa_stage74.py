"""Stage74 deterministic synthetic-PE/instruction tests; never loads vendor DLL."""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage74/audit_metadata_bridge.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage74", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def pinned_instructions():
    return {mod.BASE + rva: mod.stage72.normalize_asm(asm)
            for group in mod.PINS.values() for rva, asm in group.items()}


def valid_previous():
    return {
        "status": "SOURCE_RATE_HELPER_TWO_CANDIDATES_RUNTIME_PARENT_UNPROVEN",
        "passed_rate_provenance": {"rate_xmm9_cfg": {
            "possible_xmm9_sources": ["conditional_f32_fallback_48000",
                                      "f64_metadata_object_plus_0x18_to_f32"]}}
    }


class Stage74Tests(unittest.TestCase):
    def test_source_only_exact_sha_virtual_negative_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(sum(map(len, mod.PINS.values())), 47)
        self.assertEqual(len(mod.PINS), 6)
        self.assertEqual(mod.PINS["virtual_factory_bridge_0xcab10"][0xCAB81], "call r9")
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ctypes.CDLL", src)
        self.assertNotIn("frida.attach", src)
        self.assertIn('"virtual_callee_target_verified": False', src)
        self.assertIn('"f64_proven_stored_to_result_object_plus_0x18": False', src)
        self.assertIn('"specific_stage64_reverse_parent_verified": False', src)

    def test_every_native_pin_must_match_and_virtual_target_stays_indirect(self):
        original = pinned_instructions()
        result = mod.stage72.verify_pins(mod.PINS, original)
        self.assertEqual(sum(map(len, result.values())), 47)
        changed = dict(original)
        changed[mod.BASE + 0xCAB81] = "call 0x1800ca810"
        with self.assertRaisesRegex(ValueError, "0xcab81"):
            mod.stage72.verify_pins(mod.PINS, changed)

    def test_only_one_decoded_local_direct_branch_enters_metadata_read(self):
        insns = pinned_instructions()
        found = mod.local_direct_branches_to(insns, 0xE855, 0xE0E0, 0xF940)
        self.assertEqual(found, ["0xe6cd:jne"])
        # This checker explicitly does NOT resolve an indirect jump target.
        insns[mod.BASE + 0xE6A5] = "jmp rax"
        self.assertEqual(mod.local_direct_branches_to(insns, 0xE855, 0xE0E0, 0xF940), found)

    def test_second_direct_branch_prevents_unique_local_predecessor(self):
        insns = pinned_instructions()
        insns[mod.BASE + 0xE6A5] = "je 0x18000e855"
        self.assertEqual(mod.local_direct_branches_to(insns, 0xE855, 0xE0E0, 0xF940),
                         ["0xe6a5:je", "0xe6cd:jne"])

    def test_branch_truth_table_ordered_positive_zero_negative(self):
        self.assertEqual(mod.branch_on_zero_comiss(48000.0), "KEEP_METADATA")
        self.assertEqual(mod.branch_on_zero_comiss(1.0), "KEEP_METADATA")
        self.assertEqual(mod.branch_on_zero_comiss(math.inf), "KEEP_METADATA")
        for value in (0.0, -0.0, -1.0, -math.inf):
            self.assertEqual(mod.branch_on_zero_comiss(value), "FALLBACK_48000")
        self.assertEqual(mod.branch_on_zero_comiss(math.nan),
                         "UNORDERED_BRANCH_IF_MASKED_OR_FP_EXCEPTION")

    def test_offline_synthetic_gate_preserves_unresolved_virtual_boundary(self):
        class FakePE:
            def __init__(self, _):
                pass

            def owner(self, rva):
                return SimpleNamespace(start=rva, end=0xF940 if rva == 0xE0E0 else rva + 0x700)

        pins = pinned_instructions()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "test.dll"
            source.write_bytes(b"synthetic file bytes")
            with patch.object(mod.stage73, "audit", return_value=valid_previous()), \
                    patch.object(mod.stage72.previous, "PEFunctions", FakePE), \
                    patch.object(mod.stage72, "select_objdump", return_value=("objdump", "GNU")), \
                    patch.object(mod.stage72, "read_disassembly", return_value=pins):
                report = mod.audit(source)
        self.assertEqual(report["verified_native_instruction_count"], 47)
        self.assertTrue(report["claims"]["f64_reaches_unresolved_virtual_call_argument"])
        self.assertFalse(report["claims"]["f64_proven_stored_to_result_object_plus_0x18"])
        self.assertFalse(report["nested_metadata_to_virtual_factory"]["virtual_callee_target_verified"])

    def test_prior_stage73_status_and_sources_fail_closed(self):
        with patch.object(mod.stage73, "audit", return_value={"status": "UNACCEPTED"}):
            with self.assertRaisesRegex(ValueError, "Stage73 accepted"):
                mod.audit(Path("unused.dll"))
        altered = valid_previous()
        altered["passed_rate_provenance"]["rate_xmm9_cfg"]["possible_xmm9_sources"] = []
        with patch.object(mod.stage73, "audit", return_value=altered):
            with self.assertRaisesRegex(ValueError, "Stage73 source candidates"):
                mod.audit(Path("unused.dll"))

    def test_hash_gate_rejects_unpinned_fake_vendor_dll(self):
        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "5868USB.dll"
            dll.write_bytes(synthetic_pe())
            with self.assertRaisesRegex(ValueError, "SHA"):
                mod.stage72.previous.verify_dll(dll)


if __name__ == "__main__":
    unittest.main()
