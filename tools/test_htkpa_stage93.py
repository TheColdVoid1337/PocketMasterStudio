"""Stage93 deterministic negative controls; no original DLL or Frida needed."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage93/audit_dual_wav_guard_path.py"
spec = importlib.util.spec_from_file_location("stage93_guard_path", SCRIPT)
stage93 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage93
spec.loader.exec_module(stage93)


def synthetic_stage92():
    return {
        "stage": 92,
        "status": stage93.EXPECTED_STAGE92_STATUS,
        "native_hit_count": 6,
        "native_hook_count": 2,
        "native_completion_verified": False,
        "proves_same_invocation_stack_identity": False,
        "identifies_stage89_outer_caller": False,
        "new_run_same_thread_temporal_sequences": [
            {"outer_callsite_rva": "0xEB1E", "inner_callsite_rva": "0xD786", "gap_ms": 11},
            {"outer_callsite_rva": "0x11021", "inner_callsite_rva": "0xD786", "gap_ms": 10},
        ],
    }


def synthetic_anchors():
    return {
        owner: {stage93.BASE + address: stage93.stage91.stage72.normalize_asm(asm)
                for address, asm in pins.items()}
        for owner, pins in stage93.PINS.items()
    }


class Stage93SummaryTests(unittest.TestCase):
    def test_two_accepted_sanitized_windows(self):
        result = stage93.verify_stage92_summary(synthetic_stage92())
        self.assertEqual(result["outer_sites"], ["0xEB1E", "0x11021"])
        self.assertEqual(result["temporal_gaps_ms"], [11, 10])

    def test_repo_current_stage92_evidence(self):
        import json
        evidence = json.loads(stage93.STAGE92_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(stage93.verify_stage92_summary(evidence)["inner_site"], "0xD786")

    def test_wrong_prior_stage_number_rejected(self):
        evidence = synthetic_stage92()
        evidence["stage"] = 91
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            stage93.verify_stage92_summary(evidence)

    def test_wrong_prior_status_rejected(self):
        evidence = synthetic_stage92()
        evidence["status"] = "SYNTHETIC_OR_UNVERIFIED"
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            stage93.verify_stage92_summary(evidence)

    def test_extra_native_hit_rejected(self):
        evidence = synthetic_stage92()
        evidence["native_hit_count"] = 7
        with self.assertRaisesRegex(ValueError, "capture/completion"):
            stage93.verify_stage92_summary(evidence)

    def test_one_hook_rejected(self):
        evidence = synthetic_stage92()
        evidence["native_hook_count"] = 1
        with self.assertRaisesRegex(ValueError, "capture/completion"):
            stage93.verify_stage92_summary(evidence)

    def test_false_clo_completion_upcast_rejected(self):
        evidence = synthetic_stage92()
        evidence["native_completion_verified"] = True
        with self.assertRaisesRegex(ValueError, "capture/completion"):
            stage93.verify_stage92_summary(evidence)

    def test_fabricated_exact_stack_proof_rejected(self):
        evidence = synthetic_stage92()
        evidence["proves_same_invocation_stack_identity"] = True
        with self.assertRaisesRegex(ValueError, "overstated"):
            stage93.verify_stage92_summary(evidence)

    def test_fabricated_stage89_caller_rejected(self):
        evidence = synthetic_stage92()
        evidence["identifies_stage89_outer_caller"] = True
        with self.assertRaisesRegex(ValueError, "overstated"):
            stage93.verify_stage92_summary(evidence)

    def test_missing_second_window_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"].pop()
        with self.assertRaisesRegex(ValueError, "exactly two"):
            stage93.verify_stage92_summary(evidence)

    def test_duplicate_outer_callsite_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"][1]["outer_callsite_rva"] = "0xEB1E"
        with self.assertRaisesRegex(ValueError, "mapping"):
            stage93.verify_stage92_summary(evidence)

    def test_stage91_unobserved_outer_callsite_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"][1]["outer_callsite_rva"] = "0x100EB"
        with self.assertRaisesRegex(ValueError, "mapping"):
            stage93.verify_stage92_summary(evidence)

    def test_incorrect_inner_callsite_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"][0]["inner_callsite_rva"] = "0xBF364"
        with self.assertRaisesRegex(ValueError, "mapping"):
            stage93.verify_stage92_summary(evidence)

    def test_negative_gap_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"][0]["gap_ms"] = -1
        with self.assertRaisesRegex(ValueError, "chronology"):
            stage93.verify_stage92_summary(evidence)

    def test_gap_outside_bounded_window_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"][0]["gap_ms"] = 2001
        with self.assertRaisesRegex(ValueError, "chronology"):
            stage93.verify_stage92_summary(evidence)

    def test_wrong_recorded_gap_rejected(self):
        evidence = synthetic_stage92()
        evidence["new_run_same_thread_temporal_sequences"][0]["gap_ms"] = 12
        with self.assertRaisesRegex(ValueError, "accepted original"):
            stage93.verify_stage92_summary(evidence)


class Stage93OriginalStaticPinTests(unittest.TestCase):
    def test_all_25_original_branch_and_rate_anchors_synthetic(self):
        result = stage93.verify_original_guards(synthetic_anchors())
        self.assertEqual(result["exact_guard_dataflow_anchors"], 25)
        self.assertIn("0x10E70", result["original_owner_anchors"])

    def test_missing_original_owner_rejected(self):
        anchors = synthetic_anchors()
        del anchors[stage93.WRAPPER]
        with self.assertRaisesRegex(ValueError, "owner"):
            stage93.verify_original_guards(anchors)

    def test_nam_44100_conditional_branch_mutation_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.NESTED_NAM_WORKER][stage93.BASE + 0xEA0B] = "jne 0x18000ea0d"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_missing_nested_d4a0_call_rejected(self):
        anchors = synthetic_anchors()
        del anchors[stage93.NESTED_NAM_WORKER][stage93.BASE + 0xEB1E]
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_wrong_e0e0_return_register_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.WRAPPER][stage93.BASE + 0x10F84] = "movd xmm6,ebx"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_wrong_error_sentinel_comparison_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.WRAPPER][stage93.BASE + 0x10F8C] = "ucomisd xmm6,qword ptr [rip+0x23bf58]"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_wrong_wrapper_success_branch_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.WRAPPER][stage93.BASE + 0x10F96] = "je 0x180010ff6"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_flag_bypass_mutation_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.WRAPPER][stage93.BASE + 0x11005] = "jne 0x18001100b"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_wrong_target_rate_register_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.WRAPPER][stage93.BASE + 0x11016] = "movaps xmm2,xmm7"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)

    def test_missing_second_d4a0_call_rejected(self):
        anchors = synthetic_anchors()
        anchors[stage93.WRAPPER][stage93.BASE + 0x11021] = "call 0x18000e0e0"
        with self.assertRaisesRegex(ValueError, "Source anchor mismatch"):
            stage93.verify_original_guards(anchors)


if __name__ == "__main__":
    unittest.main()
