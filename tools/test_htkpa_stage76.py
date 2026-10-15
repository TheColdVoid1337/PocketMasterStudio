"""Stage76 exact-source gates and fully synthetic registry-boundary regression."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage76/audit_registry_selection.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage76", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_pins():
    return {mod.BASE + rva: mod.stage72.normalize_asm(asm)
            for group in mod.PINS.values() for rva, asm in group.items()}


def accepted_prior():
    return {
        "status": mod.stage75.STATUS,
        "important_limits": {
            "specific_call_0xcab81_targets_any_listed_method": False,
            "stage64_runtime_factory_instance_identified": False,
        },
        "claims": {"actual_stage64_virtual_factory_selected": False},
    }


class Stage76Tests(unittest.TestCase):
    def test_pinned_original_sha_and_source_only_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(len(mod.PINS), 8)
        self.assertEqual(sum(len(x) for x in mod.PINS.values()), 62)
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"stage64_factory_or_constructed_object_identified": False', src)
        self.assertIn('"registry_callback_target_resolved": False', src)
        self.assertNotIn("ctypes.CDLL", src)
        self.assertNotIn("frida.attach", src)

    def test_original_instruction_mutation_fail_closed(self):
        insns = fake_pins()
        self.assertEqual(sum(map(len, mod.stage72.verify_pins(mod.PINS, insns).values())), 62)
        for rva, incorrect in (
            (0xCAA65, "lea r8,[rbx+0x40]"),
            (0x3F626, "movabs rdx,0xcbf29ce484222326"),
            (0x3F731, "call 0x1800c64a0"),
            (0xCAB81, "call 0x1800c64a0"),
            (0xD01E3, "jmp 0x1800d025a"),
        ):
            changed = dict(insns)
            changed[mod.BASE + rva] = incorrect
            with self.subTest(rva=hex(rva)), self.assertRaisesRegex(ValueError, f"{rva:#x}"):
                mod.verify_source_links(changed)

    def test_fnv1a64_known_test_vectors(self):
        self.assertEqual(mod.fnv1a64(b""), 0xCBF29CE484222325)
        self.assertEqual(mod.fnv1a64(b"a"), 0xAF63DC4C8601EC8C)
        self.assertEqual(mod.fnv1a64(b"foobar"), 0x85944171F73967E8)
        self.assertNotEqual(mod.fnv1a64(b"sample_rate"), mod.fnv1a64(b"Sample_Rate"))

    def test_all_source_installs_match_stage75_exact_vtables(self):
        source = mod.verify_source_links(fake_pins())
        self.assertEqual(len(source["installations"]), 4)
        for name, item in source["installations"].items():
            self.assertEqual(item["vtable_rva"],
                             f"0x{mod.stage75.FACTORY_CHAINS[name]['vtable_rva']:x}")
            self.assertFalse(item["live_registry_factory_identity_proven"])

    def test_cross_stage_vtable_target_mismatch_rejected(self):
        with patch.dict(mod.stage75.FACTORY_CHAINS["family_d"], {"vtable_rva": 0x247CC8}):
            with self.assertRaisesRegex(ValueError, "family_d"):
                mod.verify_source_links(fake_pins())

    def test_prior_status_or_claim_change_rejected(self):
        for field in ("status", "specific_call_0xcab81_targets_any_listed_method",
                      "stage64_runtime_factory_instance_identified",
                      "actual_stage64_virtual_factory_selected"):
            prior = accepted_prior()
            if field == "status":
                prior["status"] = "WRONG"
            elif field in prior["important_limits"]:
                prior["important_limits"][field] = True
            else:
                prior["claims"][field] = True
            with self.subTest(field=field), patch.object(mod.stage75, "audit", return_value=prior):
                with self.assertRaises(ValueError):
                    mod.audit(Path("missing.dll"))

    def test_synthetic_owners_and_lookup_does_not_prove_runtime_selection(self):
        class FakePE:
            def __init__(self, _data):
                pass

            def owner(self, rva):
                return SimpleNamespace(start=rva, end=rva + 0x200)

        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "dummy.dll"
            dll.write_bytes(b"offline synthetic, never execute")
            with patch.object(mod.stage75, "audit", return_value=accepted_prior()), \
                    patch.object(mod.stage72.previous, "PEFunctions", FakePE), \
                    patch.object(mod.stage72, "select_objdump", return_value=("objdump", "GNU")), \
                    patch.object(mod.stage72, "read_disassembly", return_value=fake_pins()):
                report = mod.audit(dll)
        self.assertEqual(report["verified_native_instruction_count"], 62)
        self.assertTrue(report["claims"]["two_indirect_callback_boundaries_verified"])
        self.assertTrue(report["claims"]["four_candidate_vtables_installed_by_source_code"])
        self.assertFalse(report["claims"]["stage64_factory_or_constructed_object_identified"])
        self.assertFalse(report["registry_access"]["registry_entries_enumerated"])
        self.assertFalse(report["selected_factory_pointer_transfer"]["specific_factory_vtable_resolved"])

    def test_sha_gate_forbids_synthetic_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "5868USB.dll"
            dll.write_bytes(synthetic_pe())
            with self.assertRaisesRegex(ValueError, "SHA"):
                mod.stage72.previous.verify_dll(dll)


if __name__ == "__main__":
    unittest.main()
