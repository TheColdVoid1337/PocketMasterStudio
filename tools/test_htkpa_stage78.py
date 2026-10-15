"""Stage78 synthetic, offline, fail-closed provenance and NAM RTTI coverage."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_htkpa_stage70 import synthetic_pe

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage78/audit_architecture_provenance.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage78", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_instructions():
    return {mod.BASE + rva: mod.stage72.normalize_asm(asm)
            for group in mod.PINS.values() for rva, asm in group.items()}


def fake_file_ranges():
    result = {}
    strings = [(mod.ARCHITECTURE_LITERAL_RVA, "architecture")]
    strings += list(mod.RTTI_NAMES.values())
    for rva, value in strings:
        raw = value.encode("ascii") + b"\0"
        for offset in range(0, len(raw), 16):
            chunk = raw[offset:offset + 16]
            result[(rva + offset, len(chunk))] = chunk
    return result


def fake_previous():
    return {
        "status": mod.stage77.STATUS,
        "named_static_registrations": {k: {} for k in mod.stage77.REGISTRATIONS},
        "claims": {
            "specific_stage64_registry_key_identified": False,
            "specific_stage64_factory_selected": False,
            "original_dll_executed": False,
        },
    }


class Stage78Tests(unittest.TestCase):
    def test_exact_vendor_pin_and_source_only_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(sum(map(len, mod.PINS.values())), 38)
        self.assertEqual(set(mod.OWNER_STARTS), set(mod.PINS))
        src = SCRIPT.read_text(encoding="utf-8")
        for marker in ('"original_dll_executed": False',
                       '"specific_stage64_architecture_key_identified": False',
                       '"upstream_code_identity_or_release_verified": False',
                       '"new_hook_or_dsp_patch": False'):
            self.assertIn(marker, src)
        self.assertNotIn("ctypes.CDLL", src)
        self.assertNotIn("frida.attach", src)

    def test_exact_json_key_to_packet_and_registry_call_pins(self):
        insns = fake_instructions()
        validated = mod.stage72.verify_pins(mod.PINS, insns)
        self.assertEqual(sum(map(len, validated.values())), 38)
        self.assertEqual(mod.ARCHITECTURE_LITERAL_RVA, 0xCB44F + 7 + 0xC443A)
        self.assertEqual(mod.PINS["json_architecture_reader"][0xCB46D],
                         "lea rsi,[r14+0x20]")
        self.assertEqual(mod.PINS["metadata_marshaller"][0xCAFE3],
                         "lea rdx,[r13+0x20]")
        self.assertEqual(mod.PINS["metadata_packet"][0xCAA65],
                         "lea r8,[rbx+0x20]")

    def test_mutated_architecture_property_copy_or_lookup_fails_closed(self):
        original = fake_instructions()
        for rva, replacement in (
            (0xCB44F, "lea rdx,[rip+0xc443b]"),
            (0xCB459, "call 0x18002d2d0"),
            (0xCB46D, "lea rsi,[r14+0x40]"),
            (0xCB481, "movups xmmword ptr [rsi+0x20],xmm0"),
            (0xCAFCE, "call 0x1800cbe00"),
            (0xCAFE3, "lea rdx,[r13+0x40]"),
            (0xCB042, "call 0x1800ca810"),
            (0xCAA65, "lea r8,[rbx+0x40]"),
            (0x3F731, "call r10"),
        ):
            changed = dict(original)
            changed[mod.BASE + rva] = replacement
            with self.subTest(rva=hex(rva)), self.assertRaisesRegex(ValueError, f"{rva:#x}"):
                mod.stage72.verify_pins(mod.PINS, changed)

    def test_exact_json_literal_and_five_rtti_namespace_hints(self):
        ranges = fake_file_ranges()
        with patch.object(mod.stage72, "pe_file_bytes", side_effect=lambda _, rva, n: ranges[(rva, n)]):
            result = mod.verify_architecture_source(fake_instructions(), b"synthetic")
        self.assertEqual(result["architecture_json_key"], "architecture")
        self.assertEqual(set(result["native_rtti_class_hints"]), set(mod.RTTI_NAMES))
        self.assertTrue(all("@nam@@" in x["decorated_name"]
                            for x in result["native_rtti_class_hints"].values()))

    def test_wrong_json_field_or_rtti_class_literal_fails_closed(self):
        for rva, original, corrupted in (
            (mod.ARCHITECTURE_LITERAL_RVA, "architecture", "architecturf"),
            (mod.RTTI_NAMES["WaveNet"][0], mod.RTTI_NAMES["WaveNet"][1],
             mod.RTTI_NAMES["WaveNet"][1].replace("WaveNet", "WaveNex")),
            (mod.RTTI_NAMES["A2FastModel_encoded_specialization"][0],
             mod.RTTI_NAMES["A2FastModel_encoded_specialization"][1],
             mod.RTTI_NAMES["A2FastModel_encoded_specialization"][1].replace("nam@@", "nax@@")),
        ):
            ranges = fake_file_ranges()
            orig = original.encode("ascii") + b"\0"
            wrong = corrupted.encode("ascii") + b"\0"
            self.assertEqual(len(orig), len(wrong))
            for off in range(0, len(orig), 16):
                ranges[(rva + off, len(orig[off:off + 16]))] = wrong[off:off + 16]
            with self.subTest(rva=hex(rva)), patch.object(mod.stage72, "pe_file_bytes",
                side_effect=lambda _, rva, n: ranges[(rva, n)]), self.assertRaises(ValueError):
                mod.verify_architecture_source(fake_instructions(), b"synthetic")

    def test_unbacked_pe_architecture_literal_is_not_accepted(self):
        with self.assertRaisesRegex(ValueError, "not uniquely file-backed"):
            mod.stage77.read_literal(synthetic_pe(), mod.ARCHITECTURE_LITERAL_RVA,
                                     "architecture", 12)

    def test_prior_named_registry_runtime_claims_fail_closed(self):
        for variant in ("status", "names", "specific_stage64_registry_key_identified",
                        "specific_stage64_factory_selected", "original_dll_executed"):
            prior = fake_previous()
            if variant == "status":
                prior["status"] = "CHANGED"
            elif variant == "names":
                prior["named_static_registrations"].pop("WaveNet")
            else:
                prior["claims"][variant] = True
            with self.subTest(variant=variant), patch.object(mod.stage77, "audit", return_value=prior):
                with self.assertRaises(ValueError):
                    mod.audit(Path("unneeded.dll"))

    def test_synthetic_audit_stays_static_and_vendor_sha_gate(self):
        class FakePE:
            def __init__(self, _):
                pass

            def owner(self, entry):
                return SimpleNamespace(start=entry, end=entry + 0x500)

        ranges = fake_file_ranges()
        with tempfile.TemporaryDirectory() as tmp:
            dll = Path(tmp) / "fake.dll"
            dll.write_bytes(b"not real DLL")
            with patch.object(mod.stage77, "audit", return_value=fake_previous()), \
                    patch.object(mod.stage72.previous, "PEFunctions", FakePE), \
                    patch.object(mod.stage72, "select_objdump", return_value=("objdump", "GNU")), \
                    patch.object(mod.stage72, "read_disassembly", return_value=fake_instructions()), \
                    patch.object(mod.stage72, "pe_file_bytes", side_effect=lambda _, rva, n: ranges[(rva, n)]):
                report = mod.audit(dll)
            self.assertEqual(report["verified_native_instruction_count"], 38)
            self.assertEqual(report["json_architecture_key"]["field_name"], "architecture")
            self.assertTrue(report["claims"]["architecture_literal_and_source_to_registry_key_verified"])
            self.assertFalse(report["claims"]["specific_stage64_architecture_key_identified"])
            self.assertFalse(report["claims"]["upstream_code_identity_or_release_verified"])
            with self.assertRaisesRegex(ValueError, "SHA"):
                mod.stage72.previous.verify_dll(dll)


if __name__ == "__main__":
    unittest.main()
