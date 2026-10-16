"""Stage86 synthetic regression: exact fractional vtable/owner and honest bounds."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage86/audit_fractional_ownership.py"
spec = importlib.util.spec_from_file_location("stage86_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def synthetic_insns():
    return {owner: {mod.BASE + rva: mod.stage72.normalize_asm(asm)
                    for rva, asm in pins.items()}
            for owner, pins in mod.PINS.items()}


def synthetic_vtable():
    return {mod.FRACTIONAL_VTABLE_RVA + i * 8:
            struct.pack("<Q", mod.BASE + target)
            for i, target in enumerate(mod.VTABLE_TARGETS)}


def fake_pe_reader(blobs):
    def read(_data, rva, size):
        if rva not in blobs or size != 8:
            raise ValueError("Synthetic PE slot missing")
        return blobs[rva]
    return read


def synthetic_capture():
    config = {
        "sha256": mod.stage79.DLL_SHA256, "mode": "guarded_fractional_io",
        "sites": [{"name": "fractional_entry_io", "rva": 0x135C0,
                   "guard": {"kind": "fractional_entry_io", "vtable_rva": 0x245170}}],
        "rate_probe": {"numerator_offset": 0x1008, "denominator_offset": 0x1010},
    }
    manifest = {"hook_count": 1, "state": {"valid_field_hits": 21}}
    events = [{"kind": "hook_attached", "site": "fractional_entry_io", "rva": 0x135C0}]
    events.extend({"kind": "fractional_io", "valid": True, "observed": i,
                   "step_numerator": 88200 if i <= 4 else 96000,
                   "step_denominator": 48000 if i <= 4 else 44100}
                  for i in range(1, 22))
    return config, manifest, events


class Stage86Tests(unittest.TestCase):
    def vtable(self, blobs=None):
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=fake_pe_reader(
                blobs if blobs is not None else synthetic_vtable())):
            return mod.verify_vtable(b"FAKE_PE")

    def test_all_seven_file_backed_vtable_entries(self):
        result = self.vtable()
        self.assertEqual(len(result["seven_original_file_backed_qword_slots"]), 7)
        self.assertEqual(result["seven_original_file_backed_qword_slots"]["+0x30"], "0x135c0")

    def test_hook_slot_mutation_is_rejected(self):
        blobs = synthetic_vtable()
        blobs[0x2451A0] = struct.pack("<Q", mod.BASE + 0x135C8)
        with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
            self.vtable(blobs)

    def test_other_virtual_slot_mutation_is_rejected(self):
        blobs = synthetic_vtable()
        blobs[0x245188] = struct.pack("<Q", mod.BASE + 0x13D90)
        with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
            self.vtable(blobs)

    def test_original_instruction_count_and_owners(self):
        result = mod.verify_constructor(synthetic_insns())
        self.assertEqual(result["new_exact_instruction_pin_count"], 45)
        self.assertEqual(len(result["checked_original_instruction_rvas_by_owner"]), 3)
        self.assertTrue(result["other_constructor_branches_exist"])

    def test_missing_source_owner_fails(self):
        insns = synthetic_insns()
        insns.pop(0x11A4C)
        with self.assertRaisesRegex(ValueError, "Missing source function owner"):
            mod.verify_constructor(insns)

    def test_constructor_child_allocation_size_mutation_fails(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x12170] = "mov ecx,0x1050"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_constructor_vtable_store_mutation_fails(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x121B5] = "mov qword ptr [rsi+0x8],rax"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_constructor_numerator_offset_mutation_fails(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x121B8] = "movsd qword ptr [rsi+0x1000],xmm1"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_constructor_denominator_offset_mutation_fails(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x121C0] = "movsd qword ptr [rsi+0x1018],xmm9"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_parent_child_field_mutation_fails(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x1222A] = "mov qword ptr [rbx+0x48],rsi"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_condition_guard_mutation_fails(self):
        insns = synthetic_insns()
        insns[0x11B60][mod.BASE + 0x12151] = "je 0x1800122b7"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_capture_vtable_and_probe_binding(self):
        result = mod.verify_capture_config(*synthetic_capture())
        self.assertEqual(result["valid_fractional_io_calls"], 21)
        self.assertEqual(result["captured_runtime_parent_or_caller_metadata_keys"], [])
        self.assertFalse(result["historical_parent_instance_from_capture_verified"])

    def test_capture_vtable_mutation_fails(self):
        config, manifest, events = synthetic_capture()
        config["sites"][0]["guard"]["vtable_rva"] += 8
        with self.assertRaisesRegex(ValueError, "guard/hook/ratio"):
            mod.verify_capture_config(config, manifest, events)

    def test_capture_hook_mutation_fails(self):
        config, manifest, events = synthetic_capture()
        config["sites"][0]["rva"] += 4
        with self.assertRaisesRegex(ValueError, "guard/hook/ratio"):
            mod.verify_capture_config(config, manifest, events)

    def test_capture_numerator_offset_mutation_fails(self):
        config, manifest, events = synthetic_capture()
        config["rate_probe"]["numerator_offset"] -= 8
        with self.assertRaisesRegex(ValueError, "guard/hook/ratio"):
            mod.verify_capture_config(config, manifest, events)

    def test_capture_denominator_offset_mutation_fails(self):
        config, manifest, events = synthetic_capture()
        config["rate_probe"]["denominator_offset"] += 8
        with self.assertRaisesRegex(ValueError, "guard/hook/ratio"):
            mod.verify_capture_config(config, manifest, events)

    def test_capture_parent_field_cannot_be_silently_accepted(self):
        config, manifest, events = synthetic_capture()
        events[1]["parent_pointer"] = "0x00000000"
        with self.assertRaisesRegex(ValueError, "independent review"):
            mod.verify_capture_config(config, manifest, events)

    def test_capture_reverse_chronology_mutation_fails(self):
        config, manifest, events = synthetic_capture()
        events[-1]["step_numerator"] = 48000
        with self.assertRaisesRegex(ValueError, "chronology"):
            mod.verify_capture_config(config, manifest, events)

    def test_stage85_provenance_escalation_fails(self):
        with patch.object(mod.stage85, "audit", return_value={
            "status": mod.stage85.STATUS,
            "claims": {"historical_stage64_model_pointer_resampler_parent_bound": True,
                       "stage64_same_run_nam_clo_sha_authenticated": False,
                       "original_dll_executed": False},
        }):
            with self.assertRaisesRegex(ValueError, "elevated"):
                mod.audit(Path("absent.dll"), Path("absent.tar.gz"), {}, {})


if __name__ == "__main__":
    unittest.main()
