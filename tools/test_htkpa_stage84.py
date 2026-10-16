"""Stage84 synthetic tests: PE RTTI, constructor default and honest bounds."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage84/audit_constructor_default_rtti.py"
spec = importlib.util.spec_from_file_location("stage84_audit", SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def synthetic_instructions() -> dict[int, str]:
    return {mod.BASE + rva: mod.stage72.normalize_asm(asm)
            for group in mod.PINS.values() for rva, asm in group.items()}


def synthetic_pe() -> dict[int, bytes]:
    blobs = {}
    for _, (slot, locator) in mod.COL_POINTERS.items():
        blobs[slot] = struct.pack("<Q", mod.BASE + locator)
    blobs[0x255798] = struct.pack("<6I", 1, 0, 0, mod.CLASS_RVA,
                                  mod.HIERARCHY_RVA, 0x255798)
    blobs[0x2554B8] = struct.pack("<6I", 1, 0x50, 0, mod.CLASS_RVA,
                                  mod.HIERARCHY_RVA, 0x2554B8)
    blobs[mod.HIERARCHY_RVA] = struct.pack("<4I", 0, 1, 3, mod.BASE_ARRAY_RVA)
    blobs[mod.BASE_ARRAY_RVA] = struct.pack("<3I", *(r[0] for r in mod.BASE_DESCRIPTORS))
    for descriptor, type_rva, offset, _, decorated in mod.BASE_DESCRIPTORS:
        child_bases = 2 if type_rva == mod.CLASS_RVA else 0
        blobs[descriptor] = struct.pack("<IIiiiII", type_rva, child_bases,
                                        offset, -1, 0, 0x40, 0)
        blobs[type_rva + 0x10] = decorated.encode("ascii") + b"\0"
    return blobs


def pe_read(blobs: dict[int, bytes]):
    def read(_data: bytes, rva: int, size: int) -> bytes:
        assert 0 < size <= 16
        matches = [b[rva - address:rva - address + size]
                   for address, b in blobs.items()
                   if address <= rva and rva + size <= address + len(b)]
        if len(matches) != 1:
            raise ValueError(f"Synthetic PE range not unique: {rva:#x}")
        return matches[0]
    return read


class Stage84Tests(unittest.TestCase):
    def rtti(self, blobs=None):
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=pe_read(
                blobs if blobs is not None else synthetic_pe())):
            return mod.verify_rtti(b"FAKE_PE")

    def test_native_constructor_exact_pins(self):
        result = mod.verify_constructor(synthetic_instructions())
        self.assertEqual(sum(map(len, result["validated_instruction_groups"].values())), 16)
        self.assertFalse(result["stage64_live_initial_index_observed"])

    def test_original_rtti_subobject_and_base_names(self):
        result = self.rtti()
        self.assertEqual(result["hierarchy_base_count"], 3)
        self.assertEqual(result["verified_bases"]["DSP"]["object_offset"], "0x0")
        self.assertEqual(result["verified_bases"]["SlimmableModel"]["object_offset"], "0x50")
        self.assertEqual(result["original_col_slots"]["secondary_slimmable_interface"], "0x2554b8")

    def test_single_and_two_child_defaults_not_selector_replay(self):
        self.assertEqual(mod.default_child_index([1.0]), 0)
        self.assertEqual(mod.default_child_index([0.5, 1.0]), 1)
        self.assertEqual(mod.default_child_index([0.25, 0.75, 1.0]), 2)
        self.assertEqual(mod.stage83.select_index([0.5, 1.0], 0.25), 0)

    def test_reject_invalid_default_structures(self):
        for maxima in ([], [0.5], [0.5, 0.4], [1.0, 1.0],
                       [0.5, float("nan")], [0.5, float("inf")],
                       [True, 1.0]):
            with self.subTest(maxima=maxima), self.assertRaises(ValueError):
                mod.default_child_index(maxima)

    def test_second_col_offset_mutation_fails_closed(self):
        blobs = synthetic_pe()
        blobs[0x2554B8] = struct.pack("<6I", 1, 0, 0, mod.CLASS_RVA,
                                       mod.HIERARCHY_RVA, 0x2554B8)
        with self.assertRaisesRegex(ValueError, "locator mismatch"):
            self.rtti(blobs)

    def test_secondary_col_pointer_mutation_fails_closed(self):
        blobs = synthetic_pe()
        blobs[0x246F28] = struct.pack("<Q", mod.BASE + 0x255798)
        with self.assertRaisesRegex(ValueError, "vtable slot mismatch"):
            self.rtti(blobs)

    def test_incorrect_chd_member_count_rejected(self):
        blobs = synthetic_pe()
        blobs[mod.HIERARCHY_RVA] = struct.pack("<4I", 0, 1, 2, mod.BASE_ARRAY_RVA)
        with self.assertRaisesRegex(ValueError, "class-hierarchy"):
            self.rtti(blobs)

    def test_base_array_order_mutation_rejected(self):
        blobs = synthetic_pe()
        entries = [r[0] for r in mod.BASE_DESCRIPTORS]
        blobs[mod.BASE_ARRAY_RVA] = struct.pack("<3I", entries[0], entries[2], entries[1])
        with self.assertRaisesRegex(ValueError, "base-class array"):
            self.rtti(blobs)

    def test_slimmable_interface_displacement_mutation_rejected(self):
        blobs = synthetic_pe()
        desc = mod.BASE_DESCRIPTORS[2]
        blobs[desc[0]] = struct.pack("<IIiiiII", desc[1], 0, 0x58, -1, 0, 0x40, 0)
        with self.assertRaisesRegex(ValueError, "displacement"):
            self.rtti(blobs)

    def test_native_name_corruption_rejected(self):
        blobs = synthetic_pe()
        rva = mod.BASE_DESCRIPTORS[2][1] + 0x10
        blobs[rva] = blobs[rva].replace(b"Slimmable", b"Plimmable")
        with self.assertRaisesRegex(ValueError, "literal mismatch"):
            self.rtti(blobs)

    def test_zero_then_xchg_last_index_mutation_rejected(self):
        insns = synthetic_instructions()
        insns[mod.BASE + 0xC60E6] = "xchg qword ptr [rdi+0x68],rax"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_count_shift_mutation_rejected(self):
        insns = synthetic_instructions()
        insns[mod.BASE + 0xC6056] = "sar r9,0x3"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_nonempty_guard_mutation_rejected(self):
        insns = synthetic_instructions()
        insns[mod.BASE + 0xC6045] = "jne 0x1800c6226"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            mod.verify_constructor(insns)

    def test_prior_stage83_runtime_claim_escalation_rejected(self):
        with patch.object(mod.stage83, "audit", return_value={
            "status": mod.stage83.STATUS,
            "claims": {"stage64_selected_child_index_verified": True,
                       "stage64_resampler_parent_verified": False},
        }):
            with self.assertRaisesRegex(ValueError, "Stage83"):
                mod.audit(Path("absent.dll"), Path("absent.tar.gz"), {}, {})


if __name__ == "__main__":
    unittest.main()
