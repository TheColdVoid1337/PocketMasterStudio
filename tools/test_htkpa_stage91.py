"""Stage91 synthetic negative controls; no private vendor binary is required."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage91/audit_upstream_wav_callers.py"
spec = importlib.util.spec_from_file_location("stage91_upstream_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)


def disassembly(calls=None):
    calls = calls or {audit.WAV_WORKER: sorted(audit.CALLS_TO_WAV),
                      audit.NAM_WORKER: sorted(audit.CALLS_TO_NAM)}
    lines = [f" {audit.BASE + rva:x}: call {audit.BASE + target:#x}"
             for target, sites in calls.items() for rva in sites]
    return "\n".join(lines)


def native_fixture():
    """Minimal RVAs in synthetic PE-backed memory for negative-control tests."""
    memory = {}

    def write(rva, payload):
        for i, value in enumerate(payload):
            memory[rva + i] = value

    for target, sites in ((audit.WAV_WORKER, audit.CALLS_TO_WAV),
                          (audit.NAM_WORKER, audit.CALLS_TO_NAM),
                          (audit.stage88.GROUP_HELPER, (audit.RUNTIME_BOUND_INNER_CALL,))):
        for site in sites:
            write(site, b"\xe8" + struct.pack("<i", target - site - 5))
    for rva, packing, rate in ((audit.FIXED_44100_F64, "d", 44100.0),
                               (audit.FIXED_44100_F32, "f", 44100.0),
                               (audit.ERROR_SENTINEL_F64, "d", -2.0)):
        write(rva, struct.pack("<" + packing, rate))
    for rva, literal in audit.PUBLIC_NAM_STRINGS.items():
        write(rva, literal + b"\0")

    # Simplified PE32+ header and a two-export directory, all represented as
    # original RVAs. The second export is deliberately a decoy.
    header = bytearray(512)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 0x80)
    header[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", header, 0x80 + 24, 0x20B)
    struct.pack_into("<I", header, 0x80 + 24 + 112, 0x350000)
    write(0x350000, struct.pack("<IIHHIIIIIII", 0, 0, 0, 0, 0,
                               19, 2, 2, 0x350040, 0x350048, 0x350050))
    write(0x350040, struct.pack("<II", 0xAD5D0, 0x10000))
    write(0x350048, struct.pack("<II", 0x350080, 0x350100))
    write(0x350050, struct.pack("<HH", 0, 1))
    write(0x350080, b"getAppNormalWav\0")
    write(0x350100, b"OtherExport\0")

    def pe_read(_header, rva, size):
        if not 0 < size <= 16:
            raise ValueError("PE read must be small")
        return bytes(memory.get(rva + i, 0) for i in range(size))

    return bytes(header), memory, pe_read


def pinned_instruction_fixture():
    return {owner: {audit.BASE + rva: mnemonic for rva, mnemonic in pins.items()}
            for owner, pins in audit.STATIC_PINS.items()}


class Stage91SyntheticTests(unittest.TestCase):
    def test_two_exact_direct_call_inventories(self):
        calls = audit.decoded_calls(disassembly(), 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        self.assertEqual(calls[audit.WAV_WORKER], sorted(audit.CALLS_TO_WAV))
        self.assertEqual(calls[audit.NAM_WORKER], sorted(audit.CALLS_TO_NAM))

    def test_stray_out_of_text_is_ignored(self):
        raw = disassembly() + f"\n {audit.BASE + 0x200000:x}: call {audit.BASE + audit.WAV_WORKER:#x}"
        calls = audit.decoded_calls(raw, 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        self.assertEqual(len(calls[audit.WAV_WORKER]), 4)

    def test_indirect_call_is_not_miscounted(self):
        raw = disassembly() + f"\n {audit.BASE + 0xA0120:x}: call rax"
        calls = audit.decoded_calls(raw, 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        self.assertEqual(len(calls[audit.WAV_WORKER]), 4)

    def test_duplicate_site_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            audit.decoded_calls(disassembly() + "\n" + disassembly(),
                                0x1000, 0x18AE58, {audit.WAV_WORKER, audit.NAM_WORKER})

    def test_wrong_disassembly_call_site_rejected(self):
        calls = audit.decoded_calls(disassembly(), 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        calls[audit.WAV_WORKER].pop()
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            audit.verify_inventory(calls, b"SYNTH")

    def test_excessive_disassembly_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unbounded"):
            audit.decoded_calls("a" * (audit.stage88.MAX_DISASSEMBLY_CHARS + 1),
                                0, 0x18AE58, {audit.WAV_WORKER})

    def test_original_7_e8_rel32_bytes_in_synthetic_fixture(self):
        header, _, pe_read = native_fixture()
        calls = audit.decoded_calls(disassembly(), 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            result = audit.verify_inventory(calls, header)
        self.assertEqual(result["original_exact_e8_rel32_verified"], 7)
        self.assertTrue(result["stage89_inner_call_d786_to_ce00_still_original"])

    def test_tampered_rel32_target_rejected(self):
        header, memory, pe_read = native_fixture()
        memory[0xEB1E + 1] ^= 0x01
        calls = audit.decoded_calls(disassembly(), 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            with self.assertRaisesRegex(ValueError, "different target"):
                audit.verify_inventory(calls, header)

    def test_tampered_stage89_inner_call_rejected(self):
        header, memory, pe_read = native_fixture()
        memory[audit.RUNTIME_BOUND_INNER_CALL] = 0x90
        calls = audit.decoded_calls(disassembly(), 0x1000, 0x18AE58,
                                    {audit.WAV_WORKER, audit.NAM_WORKER})
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            with self.assertRaisesRegex(ValueError, "not five-byte E8"):
                audit.verify_inventory(calls, header)

    def test_all_original_instruction_pins_synthetic(self):
        insns = pinned_instruction_fixture()
        result = audit.verify_pins(insns)
        self.assertEqual(result["exact_instruction_anchors"], 40)
        self.assertEqual(len(result["original_function_owners"]), 4)

    def test_missing_nam_log_reference_rejected(self):
        insns = pinned_instruction_fixture()
        del insns[0xE0E0][audit.BASE + 0xE2A0]
        with self.assertRaises((ValueError, AssertionError)):
            audit.verify_pins(insns)

    def test_wrong_44100_rate_arg_rejected(self):
        insns = pinned_instruction_fixture()
        insns[0xFF40][audit.BASE + 0x100DA] = "movaps xmm2,xmm0"
        with self.assertRaises((ValueError, AssertionError)):
            audit.verify_pins(insns)

    def test_wrong_dynamic_rate_arg_rejected(self):
        insns = pinned_instruction_fixture()
        insns[0x10E70][audit.BASE + 0x11016] = "movaps xmm2,xmm9"
        with self.assertRaises((ValueError, AssertionError)):
            audit.verify_pins(insns)

    def test_wrong_export_forwarding_rejected(self):
        insns = pinned_instruction_fixture()
        insns[0xAD5D0][audit.BASE + 0xAD5E6] = "movaps xmm2,xmm0"
        with self.assertRaises((ValueError, AssertionError)):
            audit.verify_pins(insns)

    def test_literal_rate_sentinel_and_nam_strings(self):
        header, _, pe_read = native_fixture()
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            result = audit.verify_literals(header)
        self.assertEqual(result["double_error_sentinel"], -2)
        self.assertEqual(result["rdata_nam_wav_diagnostic_literals_verified"], 5)

    def test_corrupted_rate_literal_rejected(self):
        header, memory, pe_read = native_fixture()
        memory[audit.FIXED_44100_F64] ^= 0x20
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            with self.assertRaisesRegex(ValueError, "literal mismatch"):
                audit.verify_literals(header)

    def test_corrupted_error_sentinel_rejected(self):
        header, memory, pe_read = native_fixture()
        memory[audit.ERROR_SENTINEL_F64 + 7] ^= 0x10
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            with self.assertRaisesRegex(ValueError, "literal mismatch"):
                audit.verify_literals(header)

    def test_corrupted_nam_diagnostic_rejected(self):
        header, memory, pe_read = native_fixture()
        memory[0x2446D8] ^= 0x01
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            with self.assertRaisesRegex(ValueError, "NAM/WAV diagnostic"):
                audit.verify_literals(header)

    def test_bounded_pe_read_refuses_unbounded_request(self):
        with self.assertRaisesRegex(ValueError, "Unbounded"):
            audit.read_bounded_pe_bytes(b"SYNTH", 0x1000, 257)

    def test_valid_export_ordinal_and_rva(self):
        header, _, pe_read = native_fixture()
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            exports = audit.read_pe_exports(header)
        self.assertEqual(exports["getAppNormalWav"], (19, 0xAD5D0))
        self.assertEqual(audit.verify_export(exports)["ordinal"], 19)

    def test_modified_export_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "export RVA/ordinal"):
            audit.verify_export({"getAppNormalWav": (19, 0xAD5D1)})

    def test_modified_export_ordinal_rejected(self):
        with self.assertRaisesRegex(ValueError, "export RVA/ordinal"):
            audit.verify_export({"getAppNormalWav": (18, 0xAD5D0)})

    def test_duplicated_export_name_rejected(self):
        header, memory, pe_read = native_fixture()
        for i, value in enumerate(b"getAppNormalWav\0"):
            memory[0x350100 + i] = value
        with patch.object(audit.stage72, "pe_file_bytes", side_effect=pe_read):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                audit.read_pe_exports(header)

    def test_malformed_pe_header_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing MZ"):
            audit.read_pe_exports(b"\0" * 512)

    def test_stage89_does_not_bind_outer_caller(self):
        self.assertEqual(audit.RUNTIME_BOUND_INNER_CALL, 0xD786)
        self.assertEqual(audit.STATIC_PINS[0xE0E0][0xEB1E], "call 0x18000d4a0")
        self.assertEqual(len(audit.CALLS_TO_WAV), 4)
        self.assertIn("UPSTREAM_UNBOUND", audit.STATUS)


if __name__ == "__main__":
    unittest.main()
