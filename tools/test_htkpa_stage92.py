"""Stage92 private-capture protocol and adversarial offline synthetic controls."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage92/audit_outer_caller_capture.py"
CONFIG = ROOT / "research/htkpa/stages/stage92/frida.json"
spec = importlib.util.spec_from_file_location("stage92_outer_capture_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)

BASE = 0x7FFD83000000


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def fixture(outer_call=0xEB1E, inner_call=0xD786, outer_tid=77, inner_tid=77):
    manifest = {
        "status": "CAPTURED_HOOKS_ONLY",
        "expected_sha256": audit.EXPECTED_SHA, "hook_count": 2,
        "completion_verified": False,
        "state": {"runtime_verified": True, "ready": True, "hook_errors": 0,
                  "field_errors": 0, "hits": 2,
                  "site_hits": {"wav_worker_d4a0_entry": 1,
                                "resampler_ce00_entry": 1}},
    }
    events = [
        {"kind": "module_loaded", "timestamp_ms": 1000, "thread": 77,
         "base": hex(BASE), "path": r"C:\\Manager\\5868USB.dll",
         "runtime_sha256": audit.EXPECTED_SHA},
        {"kind": "hook_attached", "timestamp_ms": 1001, "thread": 77,
         "site": "wav_worker_d4a0_entry", "rva": 0xD4A0},
        {"kind": "hook_attached", "timestamp_ms": 1001, "thread": 77,
         "site": "resampler_ce00_entry", "rva": 0xCE00},
        {"kind": "ready", "timestamp_ms": 1002, "thread": 77,
         "installed": 2, "requested": 2},
        {"kind": "hit", "timestamp_ms": 1003, "thread": outer_tid,
         "site": "wav_worker_d4a0_entry", "rva": 0xD4A0,
         "pc": hex(BASE + 0xD4A0),
         "fields": {"return_address": {"value": hex(BASE + outer_call + 5)}}},
        {"kind": "hit", "timestamp_ms": 1012, "thread": inner_tid,
         "site": "resampler_ce00_entry", "rva": 0xCE00,
         "pc": hex(BASE + 0xCE00),
         "fields": {"return_address": {"value": hex(BASE + inner_call + 5)}}},
    ]
    return manifest, events


def synthetic_audit(manifest=None, events=None, config_value=None, owners=None):
    m, e = fixture()
    m = m if manifest is None else manifest
    e = e if events is None else events
    mapping = {0xEB1E: 0xE0E0, 0x100EB: 0xFF40,
               0x11021: 0x10E70, 0xAD5E9: 0xAD5D0,
               0xD786: 0xD4A0, 0xBF364: 0xBE830}
    if owners is not None:
        mapping = owners
    with patch.object(audit, "verify_original_dll") as original, \
         patch.object(audit, "original_direct_owner", side_effect=lambda data, site, target: mapping.get(site)):
        result = audit.audit(m, e, config() if config_value is None else config_value,
                             b"SYNTHETIC_NOT_ORIGINAL", "0" * 64)
        original.assert_called_once()
    return result


class Stage92ProtocolTests(unittest.TestCase):
    def test_checked_in_two_site_metadata_config(self):
        audit.validate_config(config())
        self.assertEqual(len(config()["sites"]), 2)

    def test_normalized_config_is_also_accepted(self):
        normalized = config()
        for site in normalized["sites"]:
            site["rva"] = int(site.pop("address"), 0)
            site["fields"][0]["count"] = 1
        audit.validate_config(normalized)

    def test_no_third_site(self):
        data = config()
        data["sites"].append(copy.deepcopy(data["sites"][0]))
        with self.assertRaisesRegex(ValueError, "exactly two"):
            audit.validate_config(data)

    def test_cannot_switch_to_guarded_or_binary_mode(self):
        data = config()
        data["mode"] = "guarded_f64_binary"
        with self.assertRaisesRegex(ValueError, "top-level"):
            audit.validate_config(data)

    def test_no_xmm_or_sample_payload(self):
        data = config()
        data["sites"][0]["fields"][0]["type"] = "xmm_f32"
        with self.assertRaisesRegex(ValueError, "no audio"):
            audit.validate_config(data)

    def test_no_extra_pointer_or_filename_fields(self):
        data = config()
        data["sites"][1]["fields"].append({"name": "file", "type": "ptr", "reg": "rdx"})
        with self.assertRaisesRegex(ValueError, "Only return-address"):
            audit.validate_config(data)

    def test_hit_cap_not_expandable(self):
        data = config()
        data["sites"][0]["max_hits"] = 48
        with self.assertRaisesRegex(ValueError, "bound"):
            audit.validate_config(data)

    def test_site_hidden_option_rejected(self):
        data = config()
        data["sites"][0]["input_probe"] = True
        with self.assertRaisesRegex(ValueError, "site-level"):
            audit.validate_config(data)

    def test_both_hooks_required(self):
        data = config()
        data["sites"][1]["required"] = False
        with self.assertRaisesRegex(ValueError, "required"):
            audit.validate_config(data)

    def test_wrong_sha_rejected(self):
        data = config()
        data["sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "pinned"):
            audit.validate_config(data)

    def test_wrong_original_dll_rejected(self):
        with self.assertRaisesRegex(ValueError, "Original DLL SHA256 mismatch"):
            audit.verify_original_dll(b"NOT_VENDOR_DLL")

    def test_native_pair_is_only_new_run_temporal_evidence(self):
        result = synthetic_audit()
        self.assertEqual(result["status"], audit.MATCHED)
        self.assertEqual(result["unambiguous_same_thread_temporal_sequences"], 1)
        self.assertEqual(result["observed_outer_callers"][0]["callsite_rva"], "0xEB1E")
        self.assertEqual(result["observed_outer_callers"][0]["original_pdata_owner_rva"], "0xE0E0")
        self.assertFalse(result["proves_same_invocation_stack_identity"])
        self.assertFalse(result["identifies_historical_stage89_upstream_call"])
        self.assertFalse(result["clo_export_completed"])

    def test_any_of_four_original_outer_callers_can_be_observed(self):
        for outer in (0xEB1E, 0x100EB, 0x11021, 0xAD5E9):
            with self.subTest(outer=outer):
                m, e = fixture(outer_call=outer)
                self.assertEqual(synthetic_audit(m, e)["observed_outer_callers"][0]["callsite_rva"],
                                 f"0x{outer:X}")

    def test_two_separate_outer_to_inner_sequences_are_both_preserved(self):
        m, e = fixture()
        other_outer = copy.deepcopy(e[-2])
        other_inner = copy.deepcopy(e[-1])
        other_outer["timestamp_ms"] = 12000
        other_inner["timestamp_ms"] = 12010
        other_outer["fields"]["return_address"]["value"] = hex(BASE + 0x11021 + 5)
        e.extend([other_outer, other_inner])
        m["state"]["hits"] += 2
        m["state"]["site_hits"]["wav_worker_d4a0_entry"] += 1
        m["state"]["site_hits"]["resampler_ce00_entry"] += 1
        result = synthetic_audit(m, e)
        self.assertEqual(result["status"], audit.MATCHED)
        self.assertEqual(result["unambiguous_same_thread_temporal_sequences"], 2)
        self.assertEqual([c["callsite_rva"] for c in result["observed_outer_callers"]],
                         ["0xEB1E", "0x11021"])

    def test_other_group_family_is_reported_separately(self):
        m, e = fixture()
        other = copy.deepcopy(e[-1])
        other["timestamp_ms"] = 4000
        other["fields"]["return_address"]["value"] = hex(BASE + 0xBF364 + 5)
        e.append(other)
        m["state"]["hits"] += 1
        m["state"]["site_hits"]["resampler_ce00_entry"] += 1
        result = synthetic_audit(m, e)
        self.assertEqual(result["separate_non_d4a0_group_direct_calls"], ["0xBF364"])
        self.assertEqual(result["unambiguous_same_thread_temporal_sequences"], 1)

    def test_wrong_inner_branch_is_not_a_pair(self):
        m, e = fixture(inner_call=0xBF364)
        result = synthetic_audit(m, e)
        self.assertEqual(result["status"], audit.UNBOUND)

    def test_unknown_outer_is_not_attributed_to_four_direct_calls(self):
        m, e = fixture(outer_call=0xE000)
        self.assertEqual(synthetic_audit(m, e)["status"], audit.UNBOUND)

    def test_cross_thread_is_not_a_pair(self):
        m, e = fixture(outer_tid=7, inner_tid=8)
        self.assertEqual(synthetic_audit(m, e)["status"], audit.UNBOUND)

    def test_long_gap_is_not_a_pair(self):
        m, e = fixture()
        e[-1]["timestamp_ms"] = 4000
        self.assertEqual(synthetic_audit(m, e)["status"], audit.UNBOUND)

    def test_two_outer_hits_make_selection_ambiguous(self):
        m, e = fixture()
        another = copy.deepcopy(e[-2])
        another["timestamp_ms"] = 1008
        another["fields"]["return_address"]["value"] = hex(BASE + 0x100EB + 5)
        e.insert(-1, another)
        m["state"]["hits"] += 1
        m["state"]["site_hits"]["wav_worker_d4a0_entry"] += 1
        self.assertEqual(synthetic_audit(m, e)["status"], audit.UNBOUND)

    def test_aslr_pc_mismatch_rejected(self):
        m, e = fixture()
        e[-1]["pc"] = hex(BASE + 0xCE01)
        with self.assertRaisesRegex(ValueError, "ASLR"):
            synthetic_audit(m, e)

    def test_unreadable_return_address_rejected(self):
        m, e = fixture()
        e[-2]["fields"]["return_address"] = {"error": "stack read failed"}
        with self.assertRaisesRegex(ValueError, "return_address"):
            synthetic_audit(m, e)

    def test_frida_field_error_rejected(self):
        m, e = fixture()
        m["state"]["field_errors"] = 1
        with self.assertRaisesRegex(ValueError, "Frida errors"):
            synthetic_audit(m, e)

    def test_manifest_does_not_claim_completed_clo(self):
        m, e = fixture()
        m["completion_verified"] = True
        with self.assertRaisesRegex(ValueError, "completion claim"):
            synthetic_audit(m, e)

    def test_blocked_capture_cannot_claim_runtime(self):
        m, e = fixture()
        m["status"] = "BLOCKED"
        with self.assertRaisesRegex(ValueError, "Capture status"):
            synthetic_audit(m, e)

    def test_wrong_loaded_runtime_sha_rejected(self):
        m, e = fixture()
        e[0]["runtime_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "runtime module"):
            synthetic_audit(m, e)

    def test_missing_hook_rejected(self):
        m, e = fixture()
        e.pop(2)
        with self.assertRaisesRegex(ValueError, "Hook installation"):
            synthetic_audit(m, e)

    def test_nonmonotonic_time_rejected(self):
        m, e = fixture()
        e[-1]["timestamp_ms"] = 1000
        with self.assertRaisesRegex(ValueError, "Nonmonotonic"):
            synthetic_audit(m, e)

    def test_zero_hits_rejected_as_unusable(self):
        m, e = fixture()
        m["state"]["hits"] = 0
        e = e[:-2]
        m["state"]["site_hits"] = {key: 0 for key in audit.SITES}
        with self.assertRaisesRegex(ValueError, "Native hit count"):
            synthetic_audit(m, e)

    def test_original_direct_call_target_byte_check(self):
        call = 0xEB1E
        encoded = b"\xE8" + struct.pack("<i", 0xD4A0 - call - 5)
        class FakePE:
            def owner(self, rva):
                return type("Owner", (), {"start": 0xE0E0})()
        with patch.object(audit.stage91.stage72, "pe_file_bytes", return_value=encoded), \
             patch.object(audit.stage91.stage72.previous, "PEFunctions", return_value=FakePE()):
            self.assertEqual(audit.original_direct_owner(b"fake", call, 0xD4A0), 0xE0E0)

    def test_original_call_byte_mutation_rejected(self):
        with patch.object(audit.stage91.stage72, "pe_file_bytes", return_value=b"\x90\0\0\0\0"):
            with self.assertRaisesRegex(ValueError, "not five-byte E8"):
                audit.original_direct_owner(b"fake", 0xEB1E, 0xD4A0)

    def test_unknown_direct_call_is_never_invented(self):
        self.assertIsNone(audit.original_direct_owner(b"fake", 0xABCD, 0xD4A0))


if __name__ == "__main__":
    unittest.main()
