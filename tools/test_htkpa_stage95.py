"""Stage95 exact E8, LEA, UCOMISD and branch checks; no private DLL needed."""

from __future__ import annotations

import importlib.util
import struct
import unittest
from pathlib import Path

from test_htkpa_stage94 import fake_pe


MODULE_FILE = (Path(__file__).resolve().parents[1] /
               "research/htkpa/stages/stage95/audit_nam_to_fitter_static_links.py")
spec = importlib.util.spec_from_file_location("audit_stage95", MODULE_FILE)
audit95 = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit95)


def fixture() -> tuple[bytes, list[dict]]:
    data = bytearray(fake_pe())
    # Relative call at RVA 0x1010 -> RVA 0x1090.
    struct.pack_into("<Bi", data, 0x210, 0xE8, 0x1090 - (0x1010 + 5))
    # RIP-relative LEA RDX at RVA 0x1050 -> RVA 0x2020.
    data[0x250:0x257] = b"\x48\x8d\x15" + struct.pack("<i", 0x2020 - (0x1050 + 7))
    # UCOMISD xmm6, [RIP+disp32] at RVA 0x1020.
    data[0x220:0x228] = b"\x66\x0f\x2e\x35" + struct.pack("<i", 0x2040 - (0x1020 + 8))
    data[0x230:0x232] = b"\x7a\x0e"          # 0x1030 -> 0x1040
    data[0x232:0x234] = b"\x75\x0c"          # 0x1032 -> 0x1040
    data[0x234:0x23a] = b"\x0f\x85" + struct.pack("<i", 0x1070 - (0x1034 + 6))
    return bytes(data), audit95.s94.pe64_sections(data)


class Stage95Tests(unittest.TestCase):
    def test_declared_edge_groups_and_expected_stage(self) -> None:
        self.assertEqual(audit95.STAGE, 95)
        self.assertEqual(sum(map(len, audit95.COMPILED_EDGES.values())), 14)
        self.assertEqual(sum(map(len, audit95.SELECTED_TEXT_XREFS.values())), 6)
        self.assertEqual(audit95.RETURN_SENTINEL_RVA, 0x24CEF0)

    def test_direct_e8_call(self) -> None:
        data, sections = fixture()
        self.assertEqual(audit95.exact_e8_target(data, sections, 0x1010), 0x1090)

    def test_direct_call_opcode_must_be_e8(self) -> None:
        data, sections = fixture()
        changed = bytearray(data)
        changed[0x210] = 0xE9
        with self.assertRaisesRegex(audit95.s94.AuditError, "missing direct E8"):
            audit95.exact_e8_target(changed, sections, 0x1010)

    def test_lea_rdx_to_text(self) -> None:
        data, sections = fixture()
        self.assertEqual(audit95.lea_target(data, sections, 0x1050, 0x15), 0x2020)
        with self.assertRaisesRegex(audit95.s94.AuditError, "LEA encoding"):
            audit95.lea_target(data, sections, 0x1050, 0x0D)

    def test_ucomisd_constant_address(self) -> None:
        data, sections = fixture()
        self.assertEqual(audit95.ucomisd_target(data, sections, 0x1020, 0x35), 0x2040)
        with self.assertRaisesRegex(audit95.s94.AuditError, "UCOMISD"):
            audit95.ucomisd_target(data, sections, 0x1020, 0x05)

    def test_all_three_conditional_branch_types(self) -> None:
        data, sections = fixture()
        self.assertEqual(audit95.branch_target(data, sections, 0x1030, "jp"), 0x1040)
        self.assertEqual(audit95.branch_target(data, sections, 0x1032, "jne_short"), 0x1040)
        self.assertEqual(audit95.branch_target(data, sections, 0x1034, "jne_near"), 0x1070)

    def test_wrong_branch_fails_closed(self) -> None:
        data, sections = fixture()
        with self.assertRaisesRegex(audit95.s94.AuditError, "changed jp opcode"):
            audit95.branch_target(data, sections, 0x1032, "jp")
        with self.assertRaises(ValueError):
            audit95.branch_target(data, sections, 0x1030, "ret")

    def test_synthetic_pe_never_passes_original_sha(self) -> None:
        data, _ = fixture()
        with self.assertRaisesRegex(audit95.s94.AuditError, "SHA256/size mismatch"):
            audit95.audit(data)


if __name__ == "__main__":
    unittest.main()
