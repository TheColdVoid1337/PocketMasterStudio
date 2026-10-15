"""Offline Stage70 tests using a synthetic PE; never loads the vendor DLL."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage70/audit_parent_calls.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage70", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def synthetic_pe(functions=None):
    if functions is None:
        functions = [
            (0xCDE0, 0xCE90),
            (0x11B60, 0x11C20),
            (0xBF300, 0xBF500),
            (0xE2800, 0xE2A00),
            (0x13000, 0x13100),
        ]
    data = bytearray(4096)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 2, 0, 0, 0, 240, 0x2022)
    opt = 0x98
    struct.pack_into("<H", data, opt, 0x20B)
    struct.pack_into("<Q", data, opt + 24, mod.IMAGE_BASE)
    struct.pack_into("<I", data, opt + 108, 16)
    struct.pack_into("<II", data, opt + 112 + 3 * 8, 0x3000, len(functions) * 12)
    section_table = opt + 240
    data[section_table:section_table + 8] = b".text\0\0\0"
    struct.pack_into("<IIII", data, section_table + 8,
                     0xF0000, 0x1000, 0x100, 0x400)
    data[section_table + 40:section_table + 48] = b".pdata\0\0"
    struct.pack_into("<IIII", data, section_table + 48,
                     0x1000, 0x3000, 0x200, 0x600)
    for i, (start, end) in enumerate(functions):
        struct.pack_into("<III", data, 0x600 + i * 12, start, end, 0x4000)
    return bytes(data)


def fake_stage69():
    return {
        "stage": 69,
        "status": "SOURCE_FIR_BEFORE_FRACTIONAL_CONFIRMED_DYNAMIC_PARENT_UNPROVEN",
        "dll_sha256": mod.DLL_SHA256,
        "stage64_sha256": mod.STAGE64_SHA256,
        "source": {
            "instruction_count": 34,
            "verified_instruction_rvas": [f"0x{n:x}" for n in range(34)],
        },
        "claims": {
            "upstream_filter_stage_exists_in_native_resampler_constructor": True,
            "specific_stage64_reverse_call_dynamic_parent_verified": False,
        },
    }


class Stage70Tests(unittest.TestCase):
    def test_pinned_source_and_static_only_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(mod.HELPER_RVA, 0xCE00)
        self.assertEqual(mod.CALLSITES, (0xE28F1, 0xBF364))
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ctypes.CDLL", script)
        self.assertNotIn("frida.attach", script)
        self.assertIn('"specific_stage64_reverse_object_linked_to_this_parent": False', script)
        self.assertIn('"vendor_complete_antialiasing_measured": False', script)

    def test_pe_runtime_function_owner_and_fail_closed(self):
        pe = mod.PEFunctions(synthetic_pe())
        self.assertEqual(pe.owner(0xE28F1), mod.Function(0xE2800, 0xE2A00))
        self.assertEqual(pe.owner(0xBF364), mod.Function(0xBF300, 0xBF500))
        self.assertEqual(pe.owner(mod.HELPER_RVA).start, 0xCDE0)
        self.assertEqual(pe.owner(mod.CONSTRUCTOR_RVA).start, 0x11B60)
        with self.assertRaisesRegex(ValueError, "unique"):
            pe.owner(0xABCDEF)
        with self.assertRaisesRegex(ValueError, "MZ"):
            mod.PEFunctions(b"Not a PE")
        invalid = bytearray(synthetic_pe())
        invalid[0x80:0x84] = b"XXXX"
        with self.assertRaisesRegex(ValueError, "signature"):
            mod.PEFunctions(bytes(invalid))

    def test_direct_call_parser_does_not_resolve_indirect_calls(self):
        asm = "\n".join([
            "18000ce10: call 0x180011b60 <.text+0x10b60>",
            "18000ce15: call qword ptr [rax + 0x30]",
            "18000ce19: jmp 0x180013000 <.text+0x12000>",
            "18000ce1e: call 0x180013000 <.text+0x12000>",
        ])
        calls, indirect = mod.direct_calls(mod.parse_disassembly(asm))
        self.assertEqual(calls, [(0xCE10, 0x11B60), (0xCE1E, 0x13000)])
        self.assertEqual(indirect, 1)
        self.assertIsNone(mod.direct_call_target("call qword ptr [rax + 0x30]"))

    def test_graph_positive_direct_path_is_only_static(self):
        pe = mod.PEFunctions(synthetic_pe())
        fixtures = {
            0xCDE0: {mod.IMAGE_BASE + 0xCE10: "call 0x180013000"},
            0x13000: {mod.IMAGE_BASE + 0x13020: "call 0x180011b60"},
            0x11B60: {mod.IMAGE_BASE + 0x11B70: "ret"},
        }
        output = mod.trace(pe, lambda start, _: fixtures.get(start, {}))
        self.assertTrue(output["path_found"])
        self.assertEqual(output["static_direct_call_path_to_constructor"],
                         ["0xcde0", "0x13000", "0x11b60"])
        self.assertEqual(len(output["direct_edges"]), 2)

    def test_graph_negative_indirect_or_budget_is_not_proof_of_absence(self):
        pe = mod.PEFunctions(synthetic_pe())
        fixture = {mod.IMAGE_BASE + 0xCE10: "call qword ptr [rax + 0x30]"}
        negative = mod.trace(pe, lambda _start, _end: fixture)
        self.assertFalse(negative["path_found"])
        self.assertEqual(negative["unresolved_indirect_call_instructions"], 1)
        # Even a trivially clipped search is explicitly labelled bounded.
        queue_fixture = {
            mod.IMAGE_BASE + 0xCE10: "call 0x180013000",
        }
        limited = mod.trace(pe, lambda _start, _end: queue_fixture,
                            max_functions=1)
        self.assertTrue(limited["bounded_search_incomplete"])

    def test_stage69_gate_requires_real_accepted_report(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stage69.json"
            good = fake_stage69()
            path.write_text(json.dumps(good), encoding="utf-8")
            mod.verify_stage69(path)
            good["claims"]["specific_stage64_reverse_call_dynamic_parent_verified"] = True
            path.write_text(json.dumps(good), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "acceptance"):
                mod.verify_stage69(path)
            with self.assertRaisesRegex(FileNotFoundError, "not found"):
                mod.verify_stage69(Path(td) / "not-here.json")

    def test_sha_gate_rejects_unpinned_vendor_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fake.dll"
            path.write_bytes(synthetic_pe())
            self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), mod.DLL_SHA256)
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                mod.verify_dll(path)


if __name__ == "__main__":
    unittest.main()
