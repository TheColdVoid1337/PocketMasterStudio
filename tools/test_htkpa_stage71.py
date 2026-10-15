"""Stage71 static NAM ancestry regression; synthetic PE only."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage71/audit_nam_ancestry.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage71", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fixture_pe():
    funcs = [
        (0xCDE0, 0xCE90), (0x11B60, 0x11C20),
        (0xABEB0, 0xABF30), (0xAC0E0, 0xAC160),
        (0xBE830, 0xBF5AE), (0xE1F70, 0xE2030),
        (0xE22A0, 0xE23A0), (0xE2640, 0xE2B87),
    ]
    data = bytearray(synthetic_pe(funcs))
    coff = 0x84
    struct.pack_into("<H", data, coff + 2, 3)
    opt = 0x98
    struct.pack_into("<II", data, opt + 112, 0x5000, 0x500)
    off = opt + 240 + 40 * 2
    data[off:off + 8] = b".edata\0\0"
    struct.pack_into("<IIII", data, off + 8, 0x700, 0x5000, 0x700, 0x900)
    directory = 0x900
    struct.pack_into("<IIIII", data, directory + 20,
                     4, 4, 0x5100, 0x5120, 0x5140)
    ordered = list(mod.NAM_EXPORT_RVAS.items())
    for index, (name, rva) in enumerate(ordered):
        struct.pack_into("<I", data, 0xA00 + index * 4, rva)
        name_rva = 0x5160 + index * 44
        struct.pack_into("<I", data, 0xA20 + index * 4, name_rva)
        struct.pack_into("<H", data, 0xA40 + index * 2, index)
        encoded = name.encode("ascii") + b"\0"
        data[0xA60 + index * 44:0xA60 + index * 44 + len(encoded)] = encoded
    return bytes(data)


def fixture_stage70():
    return {
        "stage": 70,
        "status": "STATIC_DIRECT_CALL_PATH_FOUND_RUNTIME_PARENT_UNPROVEN",
        "dll_sha256": mod.DLL_SHA256,
        "source_callsite_owners": {
            "0xe28f1": {"direct_target_rva": "0xce00"},
            "0xbf364": {"direct_target_rva": "0xce00"},
        },
        "source_call_graph": {
            "static_direct_call_path_to_constructor": ["0xce00", "0x11b60"],
            "path_found": True,
        },
        "claims": {"specific_stage64_reverse_object_linked_to_this_parent": False},
    }


class Stage71Tests(unittest.TestCase):
    def test_pins_and_source_only_guards(self):
        self.assertEqual(mod.NAM_EXPORT_RVAS["namConvertClo"], 0xE22A0)
        self.assertEqual(mod.NAM_EXPORT_RVAS["appNamConvertCloData"], 0xABEB0)
        code = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ctypes.CDLL", code)
        self.assertNotIn("frida.attach", code)
        self.assertIn('"runtime_stage64_reverse_parent_proven": False', code)
        self.assertIn('"runtime_original_48000_input_rate_proven": False', code)

    def test_export_directory_exact_named_anchors(self):
        self.assertEqual(mod.PEExports(fixture_pe()).verify_named_anchors(),
                         {n: f"0x{v:x}" for n, v in mod.NAM_EXPORT_RVAS.items()})
        bad = bytearray(fixture_pe())
        struct.pack_into("<I", bad, 0xA00, 0x12345)
        with self.assertRaisesRegex(ValueError, "namConvertCloData"):
            mod.PEExports(bytes(bad)).verify_named_anchors()
        with self.assertRaisesRegex(ValueError, "MZ"):
            mod.PEExports(b"invalid")

    def test_prior_stage70_report_gate(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stage70.json"
            report = fixture_stage70()
            path.write_text(json.dumps(report), encoding="utf-8")
            mod.verify_stage70(path)
            report["source_call_graph"]["path_found"] = False
            path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Stage70 accepted"):
                mod.verify_stage70(path)

    def test_rate_field_reads_and_candidate_r14_writes_are_only_hints(self):
        pe = mod.previous.PEFunctions(fixture_pe())
        statements = {
            0xE2640: {
                mod.previous.IMAGE_BASE + 0xE2700: "mov r14, rbx",
                mod.previous.IMAGE_BASE + 0xE28DC: "movsd xmm1, qword ptr [r14 + 0x8]",
            },
            0xBE830: {
                mod.previous.IMAGE_BASE + 0xBE900: "lea r14, [rsp + 0x40]",
                mod.previous.IMAGE_BASE + 0xBF358: "movss xmm1, dword ptr [r14 + 0x20ec0]",
            },
        }
        report = mod.rate_field_evidence(pe, lambda start, _: statements[start])
        self.assertFalse(report["0xe28f1"]["register_origin_proven"])
        self.assertFalse(report["0xbf364"]["runtime_sample_rate_value_proven"])
        self.assertEqual(report["0xe28f1"]["candidate_prior_r14_assignments"][0]["operand_category"], "register")
        self.assertEqual(report["0xbf364"]["candidate_prior_r14_assignments"][0]["operand_category"], "address_expression")
        statements[0xBE830][mod.previous.IMAGE_BASE + 0xBF358] = "mov eax, 0x40"
        with self.assertRaisesRegex(ValueError, "0xbf358"):
            mod.rate_field_evidence(pe, lambda start, _: statements[start])

    def test_named_export_direct_ancestry_two_targets(self):
        pe = mod.previous.PEFunctions(fixture_pe())
        defs = {
            0xE1F70: {mod.previous.IMAGE_BASE + 0xE1FA0: "call 0x1800e2640"},
            0xE22A0: {mod.previous.IMAGE_BASE + 0xE22C0: "call 0x1800be830"},
        }
        output = mod.trace_nam_roots(pe, lambda start, _: defs.get(start, {}))
        self.assertIsNotNone(output["static_ancestry_to_candidate_callsites"]["0xe28f1"])
        self.assertIsNotNone(output["static_ancestry_to_candidate_callsites"]["0xbf364"])
        self.assertTrue(output["source_only_not_runtime_provenance"])

    def test_indirect_calls_and_bounded_negative_are_not_silent_proof(self):
        pe = mod.previous.PEFunctions(fixture_pe())
        indirect = {mod.previous.IMAGE_BASE + 0xE1FA0: "call qword ptr [rax + 0x30]"}
        output = mod.trace_nam_roots(pe, lambda _start, _: indirect)
        self.assertTrue(all(v is None for v in output["static_ancestry_to_candidate_callsites"].values()))
        self.assertGreater(output["unresolved_indirect_call_count"], 0)
        self.assertTrue(output["source_only_not_runtime_provenance"])
        limited = mod.trace_nam_roots(pe, lambda _start, _: indirect, max_functions=1)
        self.assertTrue(limited["bounded_search_incomplete"])


if __name__ == "__main__":
    unittest.main()
