"""Stage79 private-archive metadata candidates: synthetic, read-only, fail-closed."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/htkpa/stages/stage79/audit_capture_architecture.py"
spec = importlib.util.spec_from_file_location("_htkpa_stage79", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def fake_stage78():
    return {"status": mod.stage78.STATUS,
            "claims": {
                "architecture_literal_and_source_to_registry_key_verified": True,
                "specific_stage64_architecture_key_identified": False,
                "specific_stage64_factory_selected": False,
                "original_dll_executed": False,
            }}


def fake_metadata(*, name: str | None = None):
    config = {"mode": "guarded_fractional_io", "sha256": mod.DLL_SHA256}
    manifest = {"status": "FRACTIONAL_EXTENDED_OUTPUTS_CLO_STABLE",
                "hook_count": 1, "completion_verified": True,
                "process_cleanup_status": "CLOSED_GRACEFULLY"}
    events = [{"kind": "fractional_io", "observed": i, "valid": True,
               "step_numerator": 88200 if i <= 4 else 96000,
               "step_denominator": 48000 if i <= 4 else 44100,
               "processor_pointer": "A" if i <= 2 else "B"}
              for i in range(1, 22)]
    events += [{"kind": "fractional_extended_output", "side": "forward", "observed": 1,
                "sha256": mod.FORWARD_SHA, "copied_f64": 1067},
               {"kind": "fractional_extended_output", "side": "reverse", "observed": 18,
                "sha256": mod.REVERSE_SHA, "copied_f64": 114}]
    if name is not None:
        config["converter_options"] = {"architecture": name}
        events[17]["diagnostic"] = {"architecture": "LSTM"}
    return config, manifest, events


def make_archive(path: Path, *, config=None, manifest=None, events=None,
                 duplicate_file=False, include_private_payload=True):
    default = fake_metadata()
    config = default[0] if config is None else config
    manifest = default[1] if manifest is None else manifest
    events = default[2] if events is None else events
    raw = {
        "frida_capture/config.json": json.dumps(config).encode(),
        "frida_capture/manifest.json": json.dumps(manifest).encode(),
        "frida_capture/events.jsonl": b"\n".join(json.dumps(x).encode() for x in events),
    }
    if include_private_payload:
        raw["frida_capture/native_f64_reverse.bin"] = b"NOT_AUTHORIZED_TO_READ" * 3
    with tarfile.open(path, "w:gz") as f:
        for key, body in raw.items():
            info = tarfile.TarInfo(key)
            info.size = len(body)
            f.addfile(info, io.BytesIO(body))
        if duplicate_file:
            body = raw["frida_capture/config.json"]
            info = tarfile.TarInfo("frida_capture/config.json")
            info.size = len(body)
            f.addfile(info, io.BytesIO(body))


class Stage79Tests(unittest.TestCase):
    def test_exact_private_sha_status_and_source_only_contract(self):
        self.assertEqual(mod.DLL_SHA256,
                         "fa8b3613a75de69deb49a9e72dce453312e4814a5c99bb6ea2e8a9e80debd5fa")
        self.assertEqual(mod.STAGE64_SHA256,
                         "aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff")
        src = SCRIPT.read_text(encoding="utf-8")
        for marker in ('"stage64_input_model_architecture_proven": False',
                       '"specific_stage64_factory_selected": False',
                       '"original_dll_executed": False', '"new_hook_or_dsp_patch": False'):
            self.assertIn(marker, src)
        self.assertNotIn("extractall(", src)
        self.assertNotIn("ctypes.CDLL", src)
        self.assertNotIn("frida.attach", src)

    def test_missing_archive_is_unknown_not_absence(self):
        with patch.object(mod.stage78, "audit", return_value=fake_stage78()):
            report = mod.audit(Path("not_needed.dll"))
        self.assertEqual(report["status"], mod.STATUS_ABSENT)
        self.assertIsNone(report["stage64_metadata_inspection"])
        self.assertFalse(report["claims"]["stage64_input_model_architecture_proven"])

    def test_synthetic_accepted_archive_no_architecture_key_remains_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.tar.gz"
            make_archive(path)
            result = mod.inspect_stage64_metadata(path)
        self.assertEqual(result["candidate_count"], 0)
        self.assertFalse(result["source_architecture_observed_in_capture_metadata"])
        self.assertFalse(result["specific_stage64_input_model_architecture_proven"])
        self.assertEqual(result["native_f64_payload_bytes_read"], 0)

    def test_two_metadata_names_only_unbound_candidates(self):
        config, manifest, events = fake_metadata(name="WaveNet")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.tar.gz"
            make_archive(path, config=config, manifest=manifest, events=events)
            parsed = mod.inspect_stage64_metadata(path)
        self.assertEqual([c["value"] for c in parsed["architecture_candidates"]],
                         ["WaveNet", "LSTM"])
        self.assertTrue(all(c["matches_a_stage77_registered_name"] for c in parsed["architecture_candidates"]))
        self.assertFalse(any(c["bound_to_live_stage64_factory"] for c in parsed["architecture_candidates"]))
        self.assertFalse(parsed["specific_stage64_input_model_architecture_proven"])

    def test_synthetic_full_report_candidate_status_still_does_not_claim_selected(self):
        config, manifest, events = fake_metadata(name="WaveNet")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capture.tar.gz"
            make_archive(path, config=config, manifest=manifest, events=events)
            with patch.object(mod.stage78, "audit", return_value=fake_stage78()), \
                    patch.object(mod, "verify_stage64_sha", return_value=None):
                report = mod.audit(Path("dummy.dll"), path)
        self.assertEqual(report["status"], mod.STATUS_CANDIDATE)
        self.assertEqual(report["stage64_metadata_inspection"]["candidate_count"], 2)
        self.assertFalse(report["claims"]["specific_stage64_factory_selected"])

    def test_unpinned_synthetic_archive_and_missing_archive_fail_sha_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.tar.gz"
            make_archive(path)
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                mod.verify_stage64_sha(path)
            with self.assertRaises(FileNotFoundError):
                mod.verify_stage64_sha(Path(tmp) / "missing.tar.gz")

    def test_stage64_invalid_ratio_or_missing_f64_summary_rejected(self):
        for case in ("ratio", "missing_summary", "changed_sha", "changed_config"):
            config, manifest, events = fake_metadata()
            if case == "ratio":
                events[4]["step_denominator"] = 48000
            elif case == "missing_summary":
                events.pop()
            elif case == "changed_sha":
                events[-1]["sha256"] = "0" * 64
            else:
                config["sha256"] = "untrusted"
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "fake.tar.gz"
                make_archive(path, config=config, manifest=manifest, events=events)
                with self.subTest(case=case), self.assertRaises(ValueError):
                    mod.inspect_stage64_metadata(path)

    def test_duplicate_tar_names_and_json_object_keys_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.load_strict_json(b'{"architecture":"WaveNet","architecture":"LSTM"}')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.tar.gz"
            make_archive(path, duplicate_file=True)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                mod.inspect_stage64_metadata(path)

    def test_malformed_field_and_unregistered_name_are_not_invented_as_registered(self):
        for bad in (None, 13, "", "x" * 129, "WåveNet"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                mod.explicit_architecture_candidates({"architecture": bad}, "config.json")
        result = mod.explicit_architecture_candidates({"architecture": "UnknownModel"}, "manifest.json")
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]["matches_a_stage77_registered_name"])
        self.assertFalse(result[0]["bound_to_live_stage64_factory"])

    def test_bounded_depth_is_not_silent_proof_of_absent_architecture(self):
        nested = {"architecture": "WaveNet"}
        for _ in range(mod.MAX_NESTING_DEPTH + 1):
            nested = {"submodel": nested}
        with self.assertRaisesRegex(ValueError, "nesting"):
            mod.explicit_architecture_candidates(nested, "manifest.json")

    def test_duplicate_or_unexpected_output_summary_fails_closed(self):
        _, _, events = fake_metadata()
        events.append(dict(events[-1]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate_event.tar.gz"
            make_archive(path, events=events)
            with self.assertRaisesRegex(ValueError, "summaries"):
                mod.inspect_stage64_metadata(path)

    def test_prior_stage78_runtime_or_path_claim_changes_fail_closed(self):
        for variant in ("status", "source_path", "specific_stage64_architecture_key_identified",
                        "specific_stage64_factory_selected", "original_dll_executed"):
            previous = fake_stage78()
            if variant == "status":
                previous["status"] = "WRONG"
            elif variant == "source_path":
                previous["claims"]["architecture_literal_and_source_to_registry_key_verified"] = False
            else:
                previous["claims"][variant] = True
            with self.subTest(variant=variant), patch.object(mod.stage78, "audit", return_value=previous):
                with self.assertRaises(ValueError):
                    mod.audit(Path("not_needed.dll"))


if __name__ == "__main__":
    unittest.main()
