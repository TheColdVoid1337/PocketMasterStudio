#!/usr/bin/env python3
"""Stage79: fail-closed Stage64 metadata-only architecture *candidate* gate.

Optional private tar input is SHA-pinned. Read only config/manifest/events
JSON; do not extract any native f64, WAV, or model-weight payloads. Even an
architecture name in these metadata files is not the identity of a live
Stage64 factory/object unless an independent source-file link proves it.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "stage78"))
import audit_architecture_provenance as stage78

DLL_SHA256 = stage78.DLL_SHA256
STAGE64_SHA256 = "aa32d8440b532708ce3551404f5a4292791abd31aba197003e850f61f22683ff"
FORWARD_SHA = "c2dd6839637c854b2d971b555f0d3a3b4ecde0c10e687bafbd2b9077bee5eec6"
REVERSE_SHA = "c3bb59aa369f6022c4c23f31fa180a9cc28af3839c12181c1ff631f5906a5df8"
STATUS_ABSENT = "STAGE64_PRIVATE_ARCHIVE_UNAVAILABLE_ARCHITECTURE_UNPROVEN"
STATUS_NO_KEY = "ACCEPTED_STAGE64_METADATA_HAS_NO_ARCHITECTURE_KEY_RUNTIME_UNPROVEN"
STATUS_CANDIDATE = "ACCEPTED_STAGE64_METADATA_HAS_UNBOUND_ARCHITECTURE_CANDIDATE"
MAX_MEMBERS = 256
MAX_METADATA_SIZE = 180_000
MAX_EVENTS_SIZE = 300_000
MAX_CANDIDATES = 64
MAX_NESTING_DEPTH = 6


def verify_stage64_sha(archive: Path) -> None:
    if not archive.is_file():
        raise FileNotFoundError("Private Stage64 tar.gz missing")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != STAGE64_SHA256:
        raise ValueError("Private Stage64 SHA mismatch; refusing unauthenticated metadata")


def reject_duplicate_object_keys(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("JSON duplicate object key; ambiguous metadata")
        out[key] = value
    return out


def load_strict_json(raw: bytes) -> object:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicate_object_keys)


def metadata_member(archive: tarfile.TarFile, name: str, limit: int) -> object:
    try:
        member = archive.getmember("frida_capture/" + name)
    except KeyError as exc:
        raise ValueError("Stage64 metadata member absent: " + name) from exc
    if not member.isfile() or not 0 < member.size <= limit:
        raise ValueError("Missing, nonregular or oversized Stage64 metadata: " + name)
    opened = archive.extractfile(member)
    if opened is None:
        raise ValueError("Cannot open Stage64 metadata: " + name)
    # Only exact selected JSON members are read. No whole archive extraction.
    with opened:
        raw = opened.read(limit + 1)
    if len(raw) != member.size or len(raw) > limit:
        raise ValueError("Stage64 metadata size changed during read")
    return load_strict_json(raw)


def safe_event_list(raw: bytes) -> list[dict]:
    result = []
    for row in raw.splitlines():
        if row:
            event = load_strict_json(row)
            if not isinstance(event, dict):
                raise ValueError("Stage64 event row is not an object")
            result.append(event)
            if len(result) > 4096:
                raise ValueError("Stage64 events count exceeds bound")
    return result


def explicit_architecture_candidates(document: object, source: str) -> list[dict]:
    """Find *names only*; never treat their presence as live model selection."""
    result = []

    def visit(value: object, path: str, depth: int) -> None:
        if depth > MAX_NESTING_DEPTH:
            raise ValueError("Stage64 metadata nesting exceeds complete scan bound")
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "architecture":
                    if (not isinstance(child, str) or not child or
                            len(child) > 128 or not child.isascii()):
                        raise ValueError("Malformed explicit architecture metadata value")
                    result.append({"source": source, "json_path": path + ".architecture",
                                   "value": child,
                                   "matches_a_stage77_registered_name": child in stage78.stage77.REGISTRATIONS,
                                   "bound_to_live_stage64_factory": False})
                    if len(result) > MAX_CANDIDATES:
                        raise ValueError("Too many architecture metadata candidates")
                elif isinstance(child, (dict, list)):
                    visit(child, path + "." + key, depth + 1)
        elif isinstance(value, list):
            if len(value) > 4096:
                raise ValueError("Stage64 metadata candidate array exceeds bound")
            for i, item in enumerate(value):
                if isinstance(item, (dict, list)):
                    visit(item, path + f"[{i}]", depth + 1)

    visit(document, "$", 0)
    return result


def inspect_stage64_metadata(archive_path: Path) -> dict:
    """Called only AFTER verify_stage64_sha on the exact private tar.gz."""
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS or len(members) != len({m.name for m in members}):
            raise ValueError("Stage64 excessive/duplicate archive members")
        config = metadata_member(archive, "config.json", MAX_METADATA_SIZE)
        manifest = metadata_member(archive, "manifest.json", MAX_METADATA_SIZE)
        try:
            events_member = archive.getmember("frida_capture/events.jsonl")
        except KeyError as exc:
            raise ValueError("Stage64 events metadata member absent") from exc
        if not events_member.isfile() or not 0 < events_member.size <= MAX_EVENTS_SIZE:
            raise ValueError("Stage64 events metadata missing/nonregular/oversized")
        opened = archive.extractfile(events_member)
        if opened is None:
            raise ValueError("Stage64 events JSON unavailable")
        with opened:
            raw = opened.read(MAX_EVENTS_SIZE + 1)
        if len(raw) != events_member.size or len(raw) > MAX_EVENTS_SIZE:
            raise ValueError("Stage64 events metadata changed during read")
        events = safe_event_list(raw)
    if not isinstance(config, dict) or not isinstance(manifest, dict):
        raise ValueError("Stage64 config/manifest are not JSON objects")
    if (config.get("mode") != "guarded_fractional_io" or config.get("sha256") != DLL_SHA256 or
            manifest.get("status") != "FRACTIONAL_EXTENDED_OUTPUTS_CLO_STABLE" or
            manifest.get("hook_count") != 1 or manifest.get("completion_verified") is not True or
            manifest.get("process_cleanup_status") != "CLOSED_GRACEFULLY"):
        raise ValueError("Stage64 source provenance or completion gate failed")
    calls = [e for e in events if e.get("kind") == "fractional_io"]
    if (len(calls) != 21 or [e.get("observed") for e in calls] != list(range(1, 22)) or
            not all(e.get("valid") is True for e in calls) or
            [(e.get("step_numerator"), e.get("step_denominator")) for e in calls] !=
            [(88200, 48000)] * 4 + [(96000, 44100)] * 17):
        raise ValueError("Stage64 21-call chronology is not authenticated")
    first = {e.get("processor_pointer") for e in calls[:2]}
    second = {e.get("processor_pointer") for e in calls[2:]}
    if len(first) != 1 or len(second) != 1 or None in first or None in second or first == second:
        raise ValueError("Stage64 processor chronology no longer matches Stage69")
    output_events = [e for e in events if e.get("kind") == "fractional_extended_output"]
    summaries = {e.get("side"): e for e in output_events}
    if (len(output_events) != 2 or set(summaries) != {"forward", "reverse"} or
            summaries["forward"].get("observed") != 1 or
            summaries["forward"].get("sha256") != FORWARD_SHA or
            summaries["forward"].get("copied_f64") != 1067 or
            summaries["reverse"].get("observed") != 18 or
            summaries["reverse"].get("sha256") != REVERSE_SHA or
            summaries["reverse"].get("copied_f64") != 114):
        raise ValueError("Stage64 f64 output summaries no longer match accepted capture")
    candidates = []
    candidates.extend(explicit_architecture_candidates(config, "config.json"))
    candidates.extend(explicit_architecture_candidates(manifest, "manifest.json"))
    # Events may contain unrelated hook metadata: report candidates as unbound.
    for i, event in enumerate(events):
        candidates.extend(explicit_architecture_candidates(event, f"events.jsonl[{i}]"))
        if len(candidates) > MAX_CANDIDATES:
            raise ValueError("Too many total architecture metadata candidates")
    return {
        "accepted_capture_metadata_gates": True,
        "inspected_archive_entries": ["frida_capture/config.json", "frida_capture/manifest.json",
                                      "frida_capture/events.jsonl"],
        "native_f64_payload_bytes_read": 0,
        "model_weight_bytes_read": 0,
        "architecture_candidates": candidates,
        "candidate_count": len(candidates),
        "source_architecture_observed_in_capture_metadata": bool(candidates),
        "specific_stage64_input_model_architecture_proven": False,
    }


def audit(dll: Path, stage64: Path | None = None, objdump: str | None = None) -> dict:
    previous = stage78.audit(dll, objdump)
    if previous["status"] != stage78.STATUS or not previous["claims"]["architecture_literal_and_source_to_registry_key_verified"]:
        raise ValueError("Stage78 exact-original static provenance gate changed")
    for name in ("specific_stage64_architecture_key_identified", "specific_stage64_factory_selected",
                 "original_dll_executed"):
        if previous["claims"][name]:
            raise ValueError("Stage78 source-only/runtime claim changed: " + name)

    if stage64 is None:
        inspected = None
        status = STATUS_ABSENT
    else:
        verify_stage64_sha(stage64)
        inspected = inspect_stage64_metadata(stage64)
        status = STATUS_CANDIDATE if inspected["candidate_count"] else STATUS_NO_KEY
    return {
        "stage": 79,
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "original_dll_sha256": DLL_SHA256,
        "expected_private_stage64_archive_sha256": STAGE64_SHA256,
        "prior_stage78_status_verified": previous["status"],
        "stage64_archive_provided": stage64 is not None,
        "stage64_metadata_inspection": inspected,
        "source_nam_architecture_key": "architecture",
        "registered_names": list(stage78.stage77.REGISTRATIONS),
        "interpretation": "Absent archive means NOT OBSERVED, not absent key. Exact archive metadata candidates remain unbound to a specific input NAM and live factory.",
        "claims": {
            "original_dll_executed": False,
            "source_architecture_path_rerun_and_verified": True,
            "stage64_input_model_architecture_proven": False,
            "specific_stage64_factory_selected": False,
            "complete_vendor_antialiasing_verified": False,
            "new_hook_or_dsp_patch": False,
        },
        "next_gate": "Access the exact model input NAM and independently bind its architecture to the Stage64 conversion. Archive-only metadata is insufficient without model identity provenance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--stage64", type=Path, default=None)
    parser.add_argument("--objdump", default=None)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and (args.out.resolve() == args.dll.resolve() or
                     args.stage64 is not None and args.out.resolve() == args.stage64.resolve()):
        raise ValueError("Refusing to overwrite original private input")
    report = audit(args.dll, args.stage64, args.objdump)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "stage": 79, "status": report["status"],
        "stage64_archive_provided": report["stage64_archive_provided"],
        "architecture_candidate_count": None if report["stage64_metadata_inspection"] is None
            else report["stage64_metadata_inspection"]["candidate_count"],
        "stage64_input_model_architecture_proven": False,
        "full_report_path": str(args.out) if args.out else None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError, FileNotFoundError, OSError, tarfile.TarError,
            json.JSONDecodeError, UnicodeDecodeError) as exc:
        print("[STAGE79 ERROR]", type(exc).__name__ + ":", str(exc), file=sys.stderr)
        raise SystemExit(2)
