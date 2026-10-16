"""Stage90 independent synthetic provenance and negative-control checks."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage90/audit_stage89_runtime_chain.py"
spec = importlib.util.spec_from_file_location("stage90_runtime_audit", SCRIPT)
audit = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit
spec.loader.exec_module(audit)

BASE = 0x7FFD83000000
GROUP = "0x178a1000"
PARENT = "0x178a2000"
CHILD = "0x178a3000"


def build_synthetic():
    kinds = audit.EXPECTED_SITES
    def event(site, timestamp, fields, registers=None):
        return {"kind": "hit", "timestamp_ms": timestamp, "thread": 77,
                "site": site, "rva": kinds[site][0],
                "pc": hex(BASE + kinds[site][0]),
                "fields": fields, "registers": registers or {}}

    module = {"kind": "module_loaded", "timestamp_ms": 1000,
              "base": hex(BASE), "path": r"C:\Program Files\Sonicake\assets\5868USB.dll",
              "runtime_sha256": audit.EXPECTED_DLL_SHA256}
    hooks = [{"kind": "hook_attached", "timestamp_ms": 1000,
              "site": site, "rva": rva} for site, (rva, _) in kinds.items()]
    ready = {"kind": "ready", "timestamp_ms": 1000,
             "installed": 4, "requested": 4}
    hits = [
        event("group_ce00_entry", 1001,
              {"return_address": {"value": hex(BASE + 0xD78B)},
               "group_input_pointer": {"value": GROUP},
               "source_hz_f32": {"error": "XMM unavailable"},
               "target_hz_f32": {"error": "XMM unavailable"}}),
        event("group_parent_install", 1004,
              {"group_input_pointer": {"value": GROUP},
               "parent_pointer": {"value": PARENT}}),
        event("parent_child_dispatch", 1020,
              {"parent_pointer": {"value": PARENT},
               "child_pointer": {"value": CHILD}}),
        event("fractional_child_entry", 1020,
              {"child_pointer": {"value": CHILD},
               "input_count_register": {"value": "0x11"}},
              {"rcx": CHILD, "r8": "0x11"}),
        event("parent_child_dispatch", 1040,
              {"parent_pointer": {"value": PARENT},
               "child_pointer": {"value": CHILD}}),
        event("fractional_child_entry", 1040,
              {"child_pointer": {"value": CHILD},
               "input_count_register": {"value": "0x12"}},
              {"rcx": CHILD, "r8": "0x12"}),
    ]
    manifest = {"status": "OPERATOR_INTERRUPTED",
                "completion_verified": False,
                "expected_sha256": audit.EXPECTED_DLL_SHA256,
                "hook_count": 4,
                "state": {"runtime_verified": True, "ready": True,
                          "hook_errors": 0, "field_errors": 2,
                          "hits": 6,
                          "site_hits": {site: count for site, (_, count) in kinds.items()}}}
    return manifest, [module, *hooks, ready, *hits]


class Stage90SyntheticTests(unittest.TestCase):
    def check(self, edit=None):
        manifest, events = build_synthetic()
        if edit:
            edit(manifest, events)
        with patch.object(audit, "verify_native_callsite", return_value=0xD4A0) as native:
            result = audit.audit(manifest, events, b"SYNTHETIC", "0" * 64)
        native.assert_called_once_with(b"SYNTHETIC", 0xD786)
        return result

    def rejected(self, edit, message):
        with self.assertRaisesRegex(ValueError, message):
            self.check(edit)

    def test_valid_chain_and_callsite(self):
        report = self.check()
        self.assertEqual(report["bound_group_callsite_rva"], "0xD786")
        self.assertEqual(report["static_pdata_function_owner_rva"], "0xD4A0")
        self.assertEqual(report["parent_same_instance_join_count"], 2)
        self.assertEqual(report["fractional_child_same_instance_join_count"], 2)
        self.assertEqual(report["hit_span_ms"], 39)

    def test_no_rate_claim_from_xmm_errors(self):
        report = self.check()
        self.assertFalse(report["rates_captured"])
        self.assertEqual(report["rate_field_read_errors"], 2)
        self.assertEqual(report["windows_crash_root_cause"], "UNKNOWN")
        self.assertFalse(report["clo_export_completion_verified"])

    def test_rate_success_flag_when_instrumented(self):
        def edit(manifest, events):
            events[6]["fields"]["source_hz_f32"] = {"value": 44100.0}
            events[6]["fields"]["target_hz_f32"] = {"value": 48000.0}
            manifest["state"]["field_errors"] = 0
        self.assertTrue(self.check(edit)["rates_captured"])

    def test_wrong_return_address_rejected(self):
        self.rejected(lambda m, e: e[6]["fields"]["return_address"].update(
            value=hex(BASE + 0x112A7)), "Unexpected Stage89 runtime callsite")

    def test_wrong_runtime_base_rejected(self):
        self.rejected(lambda m, e: e[0].update(base=hex(BASE + 0x1000)), "ASLR-relative")

    def test_wrong_module_hash_rejected(self):
        self.rejected(lambda m, e: e[0].update(runtime_sha256="f" * 64), "Runtime module SHA")

    def test_incomplete_hook_set_rejected(self):
        self.rejected(lambda m, e: e.pop(4), "Four hooks")

    def test_wrong_pc_rejected(self):
        self.rejected(lambda m, e: e[9].update(pc=hex(BASE + 0x118FE)), "ASLR-relative")

    def test_different_thread_rejected(self):
        self.rejected(lambda m, e: e[-1].update(thread=78), "multiple threads")

    def test_parent_address_swap_rejected(self):
        self.rejected(lambda m, e: e[8]["fields"]["parent_pointer"].update(
            value="0x178a9999"), "Parent dispatch")

    def test_child_address_swap_rejected(self):
        self.rejected(lambda m, e: e[10]["fields"]["child_pointer"].update(
            value="0x178a9999"), "Parent dispatch changed")

    def test_rcx_wrong_child_rejected(self):
        self.rejected(lambda m, e: e[-1]["registers"].update(rcx="0x178a9999"),
                      "Child RCX")

    def test_group_input_alias_wrong_rejected(self):
        self.rejected(lambda m, e: e[7]["fields"]["group_input_pointer"].update(
            value="0x178a9999"), "Group input pointer")

    def test_bad_chronology_rejected(self):
        self.rejected(lambda m, e: e[-1].update(timestamp_ms=1010), "Non-monotonic")

    def test_hit_before_ready_rejected(self):
        self.rejected(lambda m, e: e.insert(5, e.pop(6)), "before hooks ready")

    def test_missing_child_hit_rejected(self):
        self.rejected(lambda m, e: e.pop(), "native hit count")

    def test_successful_clo_manifest_is_not_this_capture(self):
        self.rejected(lambda m, e: m.update(completion_verified=True),
                      "completed CLO export")

    def test_manifest_hook_exception_rejected(self):
        self.rejected(lambda m, e: m["state"].update(hook_errors=1), "hook exception")

    def test_manifest_wrong_field_error_count_rejected(self):
        self.rejected(lambda m, e: m["state"].update(field_errors=0), "failed field readings")

    def test_raw_pointers_not_leaked_in_public_report(self):
        dump = str(self.check())
        for private_address in (GROUP, PARENT, CHILD, hex(BASE)):
            self.assertNotIn(private_address, dump)

    def test_stage88_callsite_owner_inventory_still_matches(self):
        self.assertEqual(audit.stage88.CALL_OWNERS[0xD786], 0xD4A0)
        self.assertEqual(audit.stage88.GROUP_HELPER, 0xCE00)

    def test_invalid_pointer_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "not hex"):
            audit.hex_pointer(None, "synthetic")
        with self.assertRaisesRegex(ValueError, "zero"):
            audit.hex_pointer("0x0", "synthetic")


if __name__ == "__main__":
    unittest.main()
