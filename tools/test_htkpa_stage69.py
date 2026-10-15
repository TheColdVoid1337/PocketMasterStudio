"""Stage69 offline regression — no vendor DLL execution, Frida or actual audio."""
from __future__ import annotations

import io
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "htkpa" / "stages" / "stage69" / "audit_topology.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage69_audit", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def make_events():
    events = []
    for observation in range(1, 22):
        step = (88200, 48000) if observation <= 4 else (96000, 44100)
        # This reproduces the address chronology observed in the native
        # metadata, not a claim of a single physical lifetime.
        pointer = "0xA" if observation <= 2 else "0xB"
        events.append({
            "kind": "fractional_io",
            "valid": True,
            "observed": observation,
            "processor_pointer": pointer,
            "step_numerator": step[0],
            "step_denominator": step[1],
        })
    events.extend([
        {"kind": "fractional_extended_output", "side": "forward",
         "observed": 1, "copied_f64": 1067,
         "sha256": mod.EXPECTED_FORWARD_SHA},
        {"kind": "fractional_extended_output", "side": "reverse",
         "observed": 18, "copied_f64": 114,
         "sha256": mod.EXPECTED_REVERSE_SHA},
    ])
    return events


def write_fixture(path, events=None, *, override_manifest=None):
    configuration = {
        "mode": "guarded_fractional_io",
        "sha256": mod.DLL_SHA256,
    }
    manifest = {
        "status": "FRACTIONAL_EXTENDED_OUTPUTS_CLO_STABLE",
        "hook_count": 1,
        "completion_verified": True,
        "process_cleanup_status": "CLOSED_GRACEFULLY",
    }
    if override_manifest:
        manifest.update(override_manifest)
    with tarfile.open(path, "w:gz") as archive:
        blocks = {
            "frida_capture/config.json": json.dumps(configuration).encode(),
            "frida_capture/manifest.json": json.dumps(manifest).encode(),
            "frida_capture/events.jsonl": b"\n".join(
                json.dumps(e).encode() for e in (events or make_events())),
        }
        for name, contents in blocks.items():
            info = tarfile.TarInfo(name)
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))


class Stage69TopologyTests(unittest.TestCase):
    def test_exact_pins_and_static_source_only_contract(self):
        self.assertEqual(mod.IMAGE_BASE, 0x180000000)
        self.assertEqual(mod.FRACTIONAL_VFTABLE_RVA, 0x245170)
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(mod.STAGE64_SHA256,
                         "aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff")
        self.assertGreaterEqual(len(mod.ANCHORS), 20)
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("ctypes.CDLL", script)
        self.assertNotIn("frida.attach", script)
        self.assertIn('"specific_stage64_reverse_call_dynamic_parent_verified": False', script)
        self.assertIn('"native_f64_payload_bytes_accessed_by_this_audit": 0', script)

    def test_parse_llvm_intel_comments_and_source_anchor_match(self):
        expected = {
            0x11BCC: "movaps xmm9, xmm2",
            0x11BD0: "movaps xmm8, xmm1",
            0x11C1E: "mov r13d, 0x2",
            0x11C62: "addsd xmm0, xmm9",
            0x11C67: "comisd xmm0, xmm8",
            0x11C6C: "jbe 0x180011f24 <.text+0x10f24>",
            0x11CEF: "mov r9d, 0x1",
            0x11CF5: "mov r8d, r13d",
            0x11CFE: "call 0x18000bdf0 <.text+0xadf0>",
            0x11D22: "mov qword ptr [rbx + 0x8], rbp",
            0x11D26: "mov dword ptr [rbx + 0x48], 0x1",
            0x11D6E: "movaps xmm0, xmm8",
            0x11D72: "addsd xmm0, xmm8",
            0x11D77: "comisd xmm0, xmm9",
            0x11D7C: "ja 0x180011f04 <.text+0x10f04>",
            0x11F1F: "jmp 0x180012170 <.text+0x11170>",
            0x121AE: "lea rax, [rip + 0x232fbb] # 0x180245170",
            0x1222A: "mov qword ptr [rbx + 0x50], rsi",
            0x118B1: "call qword ptr [rax + 0x30]",
            0x11909: "call qword ptr [rax + 0x30]",
            0xE28DC: "movsd xmm1, qword ptr [r14 + 0x8]",
            0xE28E6: "movss xmm2, dword ptr [rip + 0x16a502] # 0x18024cdf0",
            0xE28F1: "call 0x18000ce00 <.text+0xbe00>",
            0xBF34D: "movss xmm6, dword ptr [rip + 0x18da9b] # 0x18024cdf0",
            0xBF355: "movaps xmm2, xmm6",
            0xBF358: "movss xmm1, dword ptr [r14 + 0x20ec0]",
            0xBF364: "call 0x18000ce00 <.text+0xbe00>",
        }
        self.assertEqual(set(expected), set(mod.ANCHORS))
        text = "\n".join(
            f"{mod.IMAGE_BASE+rva:x}: {instruction}"
            for rva, instruction in expected.items())
        parsed = mod.parse_instruction_lines(text)
        self.assertEqual(len(mod.validate_anchors(parsed)), len(expected))
        parsed[mod.IMAGE_BASE + 0x11CFE] = "nop"
        with self.assertRaisesRegex(ValueError, "0x11cfe"):
            mod.validate_anchors(parsed)

    def test_stage64_valid_chronology_is_metadata_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "private_mock.tar.gz"
            write_fixture(path)
            report = mod.inspect_stage64(path)
            self.assertEqual(report["total_fractional_calls"], 21)
            self.assertEqual(report["original_forward_copied_f64"], 1067)
            self.assertEqual(report["original_reverse_copied_f64"], 114)
            self.assertEqual(report["processor_address_changes_between_observed"], [2, 3])
            self.assertTrue(report["same_address_appears_under_two_rate_configurations"])
            self.assertEqual(report["reinit_vs_alloc_reuse"], "NOT_DETERMINABLE_FROM_CAPTURE")
            self.assertEqual(report["native_f64_payload_bytes_accessed_by_this_audit"], 0)

    def test_stage64_fail_closed_if_ratio_sequence_or_signature_changes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "altered_mock.tar.gz"
            events = make_events()
            events[17]["step_numerator"] = 44100
            write_fixture(path, events)
            with self.assertRaisesRegex(ValueError, "chronology"):
                mod.inspect_stage64(path)
            write_fixture(path, override_manifest={"completion_verified": False})
            with self.assertRaisesRegex(ValueError, "completion"):
                mod.inspect_stage64(path)

    def test_sha_fail_closed_on_missing_and_wrong_private_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "some-other-binary.dll"
            with self.assertRaises(FileNotFoundError):
                mod.verify_pinned(path, mod.DLL_SHA256, "test")
            path.write_bytes(b"MZnot-original-private-DLL")
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                mod.verify_pinned(path, mod.DLL_SHA256, "test")


if __name__ == "__main__":
    unittest.main()
