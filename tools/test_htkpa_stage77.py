"""Stage77 synthetic offline coverage for four named registration source paths."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage77/audit_named_registry.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage77", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_instructions():
    return {mod.BASE + rva: mod.stage72.normalize_asm(asm)
            for group in mod.PINS.values() for rva, asm in group.items()}


def fake_file_backed_ranges():
    items = {}
    for name, (_, key_rva, key_size, _) in mod.REGISTRATIONS.items():
        raw = name.encode("ascii") + b"\0"
        assert len(raw) == key_size + 1
        for offset in range(0, len(raw), 16):
            chunk = raw[offset:offset + 16]
            items[(key_rva + offset, len(chunk))] = chunk
    items[(mod.WRAPPER_VTABLE_RVA + 0x10, 8)] = struct.pack("<Q", mod.BASE + mod.WRAPPER_CALLBACK_RVA)
    items[(mod.SLIMMABLE_VTABLE_RVA + 8, 8)] = struct.pack("<Q", mod.BASE + mod.SLIMMABLE_VIRTUAL_METHOD_RVA)
    return items


def fake_prior():
    return {
        "status": mod.stage76.STATUS,
        "claims": {"stage64_factory_or_constructed_object_identified": False},
        "registry_access": {
            "registry_entries_enumerated": False,
            "registry_callback_target_resolved": False,
        },
    }


class Stage77Tests(unittest.TestCase):
    def test_exact_sha_and_no_runtime_claim_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(len(mod.PINS), 10)
        self.assertEqual(sum(map(len, mod.PINS.values())), 100)
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"specific_stage64_factory_selected": False', src)
        self.assertIn('"all_runtime_registry_entries_enumerated": False', src)
        self.assertNotIn("ctypes.CDLL", src)
        self.assertNotIn("frida.attach", src)

    def test_four_distinct_named_source_registrations(self):
        self.assertEqual({k: v[3] for k, v in mod.REGISTRATIONS.items()}, {
            "SlimmableContainer": 0xC5610,
            "ConvNet": 0xC62B0,
            "LSTM": 0xCC690,
            "WaveNet": 0xD01A0,
        })
        self.assertEqual(len({v[0] for v in mod.REGISTRATIONS.values()}), 4)
        for name, (entry, _, size, _) in mod.REGISTRATIONS.items():
            self.assertEqual(len(name), size)
            self.assertEqual(mod.PINS[f"register_{name}"][entry + 0xC2], "call 0x180035ee0")

    def test_any_key_builder_callback_field_or_writer_mutation_rejected(self):
        original = fake_instructions()
        self.assertEqual(sum(map(len, mod.stage72.verify_pins(mod.PINS, original).values())), 100)
        for rva, altered in (
            (0x1A2B, "lea rax,[rip+0xc3bdf]"),
            (0x1D9D, "mov r8d,0x5"),
            (0x35F3D, "movabs rdx,0x0"),
            (0x36081, "call 0x180006a10"),
            (0x3855D, "call 0x1800c5610"),
            (0xC5F90, "movsd qword ptr [rcx+0x20],xmm2"),
        ):
            changed = dict(original)
            changed[mod.BASE + rva] = altered
            with self.subTest(rva=hex(rva)), self.assertRaisesRegex(ValueError, f"{rva:#x}"):
                mod.stage72.verify_pins(mod.PINS, changed)

    def test_exact_strings_wrapper_and_extra_method_pe_pointers(self):
        section = fake_file_backed_ranges()
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=lambda _, rva, n: section[(rva, n)]):
            verified = mod.verify_registration_links(fake_instructions(), b"synthetic")
        self.assertEqual(set(verified["registered_candidates"]), set(mod.REGISTRATIONS))
        self.assertEqual(verified["callback_method_rva"], "0x38540")
        self.assertEqual(verified["slimmable_virtual_method_rva"], "0xc56d0")

    def test_wrong_string_nul_and_pe_method_pointer_fail_closed(self):
        original = fake_file_backed_ranges()
        invalid_sets = []
        invalid = dict(original)
        invalid[(0x18F578, 8)] = b"ConvNex\0"
        invalid_sets.append(invalid)
        invalid = dict(original)
        invalid[(0x18FA24, 5)] = b"LSTM!"
        invalid_sets.append(invalid)
        invalid = dict(original)
        invalid[(mod.WRAPPER_VTABLE_RVA + 0x10, 8)] = struct.pack("<Q", mod.BASE + 0x38550)
        invalid_sets.append(invalid)
        invalid = dict(original)
        invalid[(mod.SLIMMABLE_VTABLE_RVA + 8, 8)] = struct.pack("<Q", mod.BASE + 0xC5610)
        invalid_sets.append(invalid)
        for i, section in enumerate(invalid_sets):
            with self.subTest(i=i), patch.object(mod.stage72, "pe_file_bytes",
                                                 side_effect=lambda _, rva, n: section[(rva, n)]):
                with self.assertRaises(ValueError):
                    mod.verify_registration_links(fake_instructions(), b"synthetic")

    def test_missing_or_unbacked_original_pe_data_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "not uniquely file-backed"):
            mod.read_pointer(synthetic_pe(), mod.WRAPPER_VTABLE_RVA + 0x10,
                             mod.WRAPPER_CALLBACK_RVA)
        with self.assertRaisesRegex(ValueError, "not uniquely file-backed"):
            mod.read_literal(synthetic_pe(), 0x18F488, "SlimmableContainer", 18)

    def test_prior_stage76_claims_must_remain_unresolved(self):
        cases = ["status", "stage64_factory_or_constructed_object_identified",
                 "registry_entries_enumerated", "registry_callback_target_resolved"]
        for case in cases:
            prior = fake_prior()
            if case == "status":
                prior["status"] = "WRONG"
            elif case in prior["claims"]:
                prior["claims"][case] = True
            else:
                prior["registry_access"][case] = True
            with self.subTest(case=case), patch.object(mod.stage76, "audit", return_value=prior):
                with self.assertRaises(ValueError):
                    mod.audit(Path("missing.dll"))

    def test_synthetic_source_audit_keeps_runtime_key_unknown_and_sha_gate(self):
        class FakePE:
            def __init__(self, _raw):
                pass

            def owner(self, entry):
                return SimpleNamespace(start=entry, end=entry + 0x200)

        ranges = fake_file_backed_ranges()
        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "synthetic.dll"
            dll.write_bytes(b"not vendor code")
            with patch.object(mod.stage76, "audit", return_value=fake_prior()), \
                    patch.object(mod.stage72.previous, "PEFunctions", FakePE), \
                    patch.object(mod.stage72, "select_objdump", return_value=("objdump", "GNU")), \
                    patch.object(mod.stage72, "read_disassembly", return_value=fake_instructions()), \
                    patch.object(mod.stage72, "pe_file_bytes", side_effect=lambda _, rva, n: ranges[(rva, n)]):
                report = mod.audit(dll)
            self.assertEqual(report["verified_native_instruction_count"], 100)
            self.assertTrue(report["claims"]["named_wrapper_callback_source_chain_verified"])
            self.assertTrue(report["claims"]["fifth_slimmable_vtable_and_result_f64_writer_verified"])
            self.assertFalse(report["claims"]["specific_stage64_registry_key_identified"])
            self.assertFalse(report["claims"]["specific_stage64_factory_selected"])
            dll.write_bytes(synthetic_pe())
            with self.assertRaisesRegex(ValueError, "SHA"):
                mod.stage72.previous.verify_dll(dll)


if __name__ == "__main__":
    unittest.main()
