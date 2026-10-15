"""Stage75 synthetic offline regression for PE vtable slots and indirect call gap."""
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
SCRIPT = ROOT / "research/htkpa/stages/stage75/audit_virtual_factories.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage75", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_pins():
    return {mod.BASE + rva: mod.stage72.normalize_asm(op)
            for group in mod.PINS.values() for rva, op in group.items()}


def prior():
    return {
        "status": mod.stage74.STATUS,
        "claims": {"local_nonnull_gate_verified": True},
        "nested_metadata_to_virtual_factory": {"virtual_callee_target_verified": False},
    }


class Stage75Tests(unittest.TestCase):
    def test_original_sha_pins_and_no_dynamic_proof_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(sum(map(len, mod.PINS.values())), 38)
        self.assertEqual(len(mod.PINS), 10)
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"actual_stage64_virtual_factory_selected": False', src)
        self.assertIn('"specific_call_0xcab81_targets_any_listed_method": False', src)
        self.assertNotIn("ctypes.CDLL", src)
        self.assertNotIn("frida.attach", src)

    def test_pins_fail_on_field_writer_or_changed_indirect_dispatch(self):
        insns = fake_pins()
        accepted = mod.stage72.verify_pins(mod.PINS, insns)
        self.assertEqual(sum(map(len, accepted.values())), 38)
        changed = dict(insns)
        changed[mod.BASE + 0xCA44B] = "movsd qword ptr [rcx+0x20],xmm3"
        with self.assertRaisesRegex(ValueError, "0xca44b"):
            mod.stage72.verify_pins(mod.PINS, changed)
        changed = dict(insns)
        changed[mod.BASE + 0xCAB81] = "call 0x1800c64a0"
        with self.assertRaisesRegex(ValueError, "0xcab81"):
            mod.stage72.verify_pins(mod.PINS, changed)

    def test_four_vtable_families_have_distinct_slots_and_two_direct_edges(self):
        self.assertEqual(len(mod.FACTORY_CHAINS), 4)
        self.assertEqual(len({x["vtable_rva"] for x in mod.FACTORY_CHAINS.values()}), 4)
        self.assertEqual(len({x["method_rva"] for x in mod.FACTORY_CHAINS.values()}), 4)
        asm = fake_pins()
        for chain in mod.FACTORY_CHAINS.values():
            self.assertEqual(asm[mod.BASE + chain["caller_rva"]],
                             f"call 0x{mod.BASE + chain['constructor_rva']:x}")
            self.assertEqual(asm[mod.BASE + chain["base_call_rva"]],
                             "call 0x1800ca430")
        self.assertEqual(asm[mod.BASE + 0xCAB81], "call r9")

    def test_original_pe_exact_virtual_slot_parsing_and_mutation_rejected(self):
        raw = bytearray(synthetic_pe())
        # Synthetic .text fixture: RVA 0x1010 is file offset 0x410.
        struct.pack_into("<Q", raw, 0x418, mod.BASE + 0xC64A0)
        accepted = mod.read_exact_virtual_slot(bytes(raw), 0x1010, 0xC64A0)
        self.assertEqual(accepted["virtual_method_rva"], "0xc64a0")
        with self.assertRaisesRegex(ValueError, "virtual slot mismatch"):
            mod.read_exact_virtual_slot(bytes(raw), 0x1010, 0xCC730)

    def test_pe_unbacked_vtable_does_not_pass_as_zero_or_default(self):
        with self.assertRaisesRegex(ValueError, "not uniquely file-backed"):
            mod.read_exact_virtual_slot(synthetic_pe(), 0x246FB0, 0xC64A0)
        with self.assertRaisesRegex(ValueError, "Invalid PE"):
            mod.read_exact_virtual_slot(b"garbage", 0x1010, 0xC64A0)

    def test_stage74_gate_rejects_wrong_status_and_claim(self):
        invalid = prior()
        invalid["status"] = "WRONG"
        with patch.object(mod.stage74, "audit", return_value=invalid):
            with self.assertRaisesRegex(ValueError, "Stage74 accepted"):
                mod.audit(Path("unused.dll"))
        invalid = prior()
        invalid["nested_metadata_to_virtual_factory"]["virtual_callee_target_verified"] = True
        with patch.object(mod.stage74, "audit", return_value=invalid):
            with self.assertRaisesRegex(ValueError, "virtual boundary"):
                mod.audit(Path("unused.dll"))

    def test_pure_synthetic_audit_keeps_runtime_callee_unproven(self):
        class FakePE:
            def __init__(self, _):
                pass

            def owner(self, rva):
                return SimpleNamespace(start=rva, end=rva + 0x1000)

        slots = {x["vtable_rva"] + 8: x["method_rva"] for x in mod.FACTORY_CHAINS.values()}

        def bytes_at_rva(_, rva, size):
            if size != 8 or rva not in slots:
                raise ValueError("Unexpected synthetic PE read")
            return struct.pack("<Q", mod.BASE + slots[rva])

        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "synthetic.dll"
            dll.write_bytes(b"read-only test fixture")
            with patch.object(mod.stage74, "audit", return_value=prior()), \
                    patch.object(mod.stage72.previous, "PEFunctions", FakePE), \
                    patch.object(mod.stage72, "select_objdump", return_value=("objdump", "GNU")), \
                    patch.object(mod.stage72, "read_disassembly", return_value=fake_pins()), \
                    patch.object(mod.stage72, "pe_file_bytes", side_effect=bytes_at_rva):
                report = mod.audit(dll)
        self.assertEqual(report["verified_native_instruction_count"], 38)
        self.assertEqual(len(report["candidate_vtable_method_chains"]), 4)
        self.assertTrue(report["claims"]["f64_field_writer_exists_in_base_constructor"])
        self.assertFalse(report["claims"]["actual_stage64_virtual_factory_selected"])
        self.assertFalse(report["important_limits"]["complete_dynamic_metadata_to_field_link_proven"])

    def test_original_sha_gate_rejects_synthetic_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "5868USB.dll"
            dll.write_bytes(synthetic_pe())
            with self.assertRaisesRegex(ValueError, "SHA"):
                mod.stage72.previous.verify_dll(dll)


if __name__ == "__main__":
    unittest.main()
