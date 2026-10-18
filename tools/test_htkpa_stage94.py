"""Stage94 tests: no proprietary DLL required."""

from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path


MODULE_FILE = (Path(__file__).resolve().parents[1] /
               "research/htkpa/stages/stage94/audit_public_source_fingerprints.py")
spec = importlib.util.spec_from_file_location("audit_stage94", MODULE_FILE)
audit94 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit94)


def fake_pe() -> bytes:
    """Synthetic PE32+ with one small text and one small rdata section."""
    data = bytearray(0x600)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 2, 0, 0, 0, 0xF0, 0)
    struct.pack_into("<H", data, 0x98, 0x20B)
    sections = 0x80 + 24 + 0xF0
    for at, name, rva, raw in (
        (sections, b".text", 0x1000, 0x200),
        (sections + 40, b".rdata", 0x2000, 0x400),
    ):
        data[at:at + len(name)] = name
        struct.pack_into("<IIII", data, at + 8, 0x200, rva, 0x200, raw)
    target = 0x2020
    site = 0x1010
    data[0x420:0x426] = b"NAM!!\0"
    data[0x210:0x217] = b"\x48\x8d\x15" + struct.pack("<i", target - (site + 7))
    return bytes(data)


class Stage94Tests(unittest.TestCase):
    def test_original_pins_have_known_scope(self) -> None:
        self.assertEqual(len(audit94.ORIGINAL_SHA256), 64)
        self.assertEqual(audit94.ORIGINAL_SIZE, 2_902_016)
        self.assertEqual(len(audit94.FINGERPRINTS), 12)
        self.assertEqual(sum(map(len, audit94.COMPILED_REFERENCES.values())), 4)

    def test_pe_sections_and_file_rvas(self) -> None:
        sections = audit94.pe64_sections(fake_pe())
        self.assertEqual(audit94.raw_to_rva(sections, 0x420), 0x2020)
        self.assertEqual(audit94.rva_to_raw(sections, 0x1010), 0x210)
        with self.assertRaises(audit94.AuditError):
            audit94.rva_to_raw(sections, 0x4000)

    def test_rip_lea_target(self) -> None:
        data = fake_pe()
        sections = audit94.pe64_sections(data)
        self.assertEqual(audit94.rip_lea_rdx_target(data, sections, 0x1010), 0x2020)

    def test_changed_opcode_fails_closed(self) -> None:
        data = bytearray(fake_pe())
        data[0x210] = 0x90
        with self.assertRaisesRegex(audit94.AuditError, "not expected LEA"):
            audit94.rip_lea_rdx_target(data, audit94.pe64_sections(data), 0x1010)

    def test_bad_dos_and_pe_signatures(self) -> None:
        data = bytearray(fake_pe())
        data[0] = 0x00
        with self.assertRaisesRegex(audit94.AuditError, "MZ"):
            audit94.pe64_sections(data)
        data = bytearray(fake_pe())
        data[0x80:0x84] = b"bad!"
        with self.assertRaisesRegex(audit94.AuditError, "PE signature"):
            audit94.pe64_sections(data)

    def test_wrong_arch_and_section_bounds(self) -> None:
        data = bytearray(fake_pe())
        struct.pack_into("<H", data, 0x84, 0x14C)
        with self.assertRaisesRegex(audit94.AuditError, "AMD64"):
            audit94.pe64_sections(data)
        data = bytearray(fake_pe())
        struct.pack_into("<I", data, 0x188 + 16, len(data) + 1)
        with self.assertRaisesRegex(audit94.AuditError, "raw bounds"):
            audit94.pe64_sections(data)

    def test_synthetic_binary_cannot_pass_original_sha_gate(self) -> None:
        with self.assertRaisesRegex(audit94.AuditError, "SHA256/size mismatch"):
            audit94.audit(fake_pe())


if __name__ == "__main__":
    unittest.main()
